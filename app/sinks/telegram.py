"""Telegram notifications via the Bot API (plain httpx, no bot framework needed)."""

import html
import logging

import httpx

from app.models import Lead

log = logging.getLogger(__name__)


def lead_message(lead: Lead, link: str) -> str:
    e = html.escape
    lines = [f"🔔 <b>New lead</b> · {e(lead.source)}"]
    if lead.name:
        lines.append(f"👤 {e(lead.name)}")
    if lead.phone:
        lines.append(f'📞 <a href="tel:{lead.phone}">{lead.phone}</a>')
    if lead.email:
        lines.append(f"✉️ {e(lead.email)}")
    if lead.comment:
        lines.append(f"💬 {e(lead.comment[:500])}")
    if lead.utm:
        lines.append("🏷 " + e(" ".join(f"{k}={v}" for k, v in lead.utm.items())))
    if link.startswith("http"):
        lines.append(f'<a href="{e(link)}">Open in the sheet</a>')
    else:
        lines.append(f"📄 {e(link)}")
    return "\n".join(lines)


class Telegram:
    def __init__(self, token: str, chat_ids: list[int]):
        self.token, self.chat_ids = token, chat_ids

    async def send(self, text: str) -> None:
        async with httpx.AsyncClient(timeout=15) as client:
            for chat_id in self.chat_ids:
                resp = await client.post(
                    f"https://api.telegram.org/bot{self.token}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": text,
                        "parse_mode": "HTML",
                        "link_preview_options": {"is_disabled": True},
                    },
                )
                if not resp.is_success:  # never log the URL: it contains the token
                    log.warning("Telegram error %s for chat %s", resp.status_code, chat_id)

    async def send_document(self, filename: str, content: bytes, caption: str = "") -> None:
        async with httpx.AsyncClient(timeout=30) as client:
            for chat_id in self.chat_ids:
                await client.post(
                    f"https://api.telegram.org/bot{self.token}/sendDocument",
                    data={"chat_id": str(chat_id), "caption": caption},
                    files={"document": (filename, content)},
                )


class LogNotifier:
    """Demo mode: print notifications instead of sending them."""

    async def send(self, text: str) -> None:
        log.info("[telegram demo]\n%s", text)

    async def send_document(self, filename: str, content: bytes, caption: str = "") -> None:
        log.info("[telegram demo] document %s (%d bytes) %s", filename, len(content), caption)
