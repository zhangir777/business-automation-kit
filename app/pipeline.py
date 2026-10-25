"""validate → normalize → dedupe → store → notify. If storage fails, the lead goes to a local
queue (data/queue.jsonl) and is re-sent later; the admin gets a warning."""

import asyncio
import hashlib
import json
import logging
import threading
from datetime import datetime, timedelta
from pathlib import Path

from app.models import Lead
from app.sinks.base import Notifier, Storage
from app.sinks.telegram import lead_message

log = logging.getLogger(__name__)


class Pipeline:
    def __init__(
        self,
        storage: Storage,
        notifier: Notifier,
        queue_file: Path,
        dedupe_window: timedelta = timedelta(minutes=10),
    ):
        self.storage, self.notifier = storage, notifier
        self.queue_file = queue_file
        self.dedupe_window = dedupe_window
        self._seen: dict[str, datetime] = {}
        self._queue_lock = threading.Lock()

    @staticmethod
    def fingerprint(lead: Lead) -> str:
        key = "|".join([lead.phone or "", (lead.email or "").lower(), lead.comment.strip().lower()])
        return hashlib.sha256(key.encode()).hexdigest()

    def is_duplicate(self, lead: Lead) -> bool:
        fp, now = self.fingerprint(lead), lead.created_at
        self._seen = {k: t for k, t in self._seen.items() if now - t < self.dedupe_window}
        if fp in self._seen:
            return True
        self._seen[fp] = now
        return False

    async def process(self, lead: Lead) -> str:
        """Returns 'duplicate', 'saved' or 'queued'."""
        if self.is_duplicate(lead):
            log.info("Duplicate lead ignored (%s)", lead.source)
            return "duplicate"
        try:
            link = await asyncio.to_thread(self.storage.append, lead)
            status = "saved"
        except Exception as exc:
            log.error("Storage failed, lead queued: %s", type(exc).__name__)
            self._enqueue(lead)
            link, status = "⚠️ not saved yet: storage unavailable, queued for retry", "queued"
            await self._safe_notify(
                "⚠️ Google Sheet is unavailable. The lead is saved locally and will be "
                "added automatically when the sheet is back."
            )
        await self._safe_notify(lead_message(lead, link))
        return status

    async def _safe_notify(self, text: str) -> None:
        try:
            await self.notifier.send(text)
        except Exception as exc:
            log.error("Notification failed: %s", type(exc).__name__)

    def _enqueue(self, lead: Lead) -> None:
        with self._queue_lock:
            self.queue_file.parent.mkdir(parents=True, exist_ok=True)
            with self.queue_file.open("a", encoding="utf-8") as f:
                f.write(lead.model_dump_json() + "\n")

    def queued(self) -> list[Lead]:
        if not self.queue_file.exists():
            return []
        lines = self.queue_file.read_text(encoding="utf-8").splitlines()
        return [Lead.model_validate(json.loads(line)) for line in lines if line.strip()]

    async def retry_queue(self) -> int:
        """Try to store queued leads again. Returns how many were stored."""
        with self._queue_lock:
            leads = self.queued()
            if not leads:
                return 0
            left: list[Lead] = []
            for lead in leads:
                try:
                    await asyncio.to_thread(self.storage.append, lead)
                except Exception:
                    left.append(lead)
            self.queue_file.write_text(
                "".join(lead.model_dump_json() + "\n" for lead in left), encoding="utf-8"
            )
        done = len(leads) - len(left)
        if done:
            await self._safe_notify(f"✅ {done} queued lead(s) added to the sheet.")
        return done
