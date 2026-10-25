"""FastAPI app: POST /webhook/{source}, GET /health, and scheduled jobs.

uvicorn app.main:app --port 8000
"""

import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from urllib.parse import parse_qsl

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, HTTPException, Request
from pydantic import ValidationError

from app.config import Settings, settings
from app.jobs.reports import daily_summary, stale_leads, stale_message, weekly_report
from app.pipeline import Pipeline
from app.security import RateLimiter, check_secret, read_limited_body
from app.sinks.local_xlsx import LocalXlsx
from app.sinks.telegram import LogNotifier, Telegram
from app.sources import SOURCES
from app.sources.tilda import is_test

log = logging.getLogger("app")


def build_pipeline(cfg: Settings) -> Pipeline:
    if cfg.google_enabled:
        from app.sinks.google_sheets import GoogleSheet

        storage = GoogleSheet(cfg.google_credentials_file, cfg.google_sheet_id)
        log.info("Storage: Google Sheet")
    else:
        storage = LocalXlsx(cfg.data_dir / "leads.xlsx")
        log.info("Storage: demo mode, %s", storage.path)
    if cfg.telegram_bot_token and cfg.telegram_chat_ids:
        notifier = Telegram(cfg.telegram_bot_token, cfg.telegram_chat_ids)
    else:
        notifier = LogNotifier()
        log.info("Telegram: demo mode, notifications go to the log")
    return Pipeline(
        storage, notifier, cfg.data_dir / "queue.jsonl", timedelta(minutes=cfg.dedupe_minutes)
    )


def now(cfg: Settings) -> datetime:
    return datetime.now(cfg.tz).replace(tzinfo=None)


async def run_daily(p: Pipeline, cfg: Settings) -> None:
    await p.notifier.send(daily_summary(p.storage.records(), now(cfg).date()))


async def run_weekly(p: Pipeline, cfg: Settings) -> None:
    end = now(cfg).date() - timedelta(days=1)
    content, stats = weekly_report(p.storage.records(), end)
    name = f"leads_week_{end:%Y-%m-%d}.xlsx"
    if hasattr(p.notifier, "send_document"):
        await p.notifier.send_document(name, content, f"Weekly report: {stats['total']} leads")
    if cfg.smtp_host and cfg.report_email_to:
        from app.sinks.email_smtp import EmailSmtp

        mail = EmailSmtp(
            cfg.smtp_host, cfg.smtp_port, cfg.smtp_user, cfg.smtp_password, cfg.report_email_to
        )
        await mail.send(
            f"Weekly leads report: {stats['total']}", "See attachment.", (name, content)
        )


async def run_stale(p: Pipeline, cfg: Settings) -> None:
    stale = stale_leads(p.storage.records(), now(cfg), cfg.stale_hours)
    if stale:
        await p.notifier.send(stale_message(stale, cfg.stale_hours))


def create_app(cfg: Settings = settings, pipeline: Pipeline | None = None) -> FastAPI:
    limiter = RateLimiter(cfg.rate_limit_per_minute)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.pipeline = pipeline or build_pipeline(cfg)
        p = app.state.pipeline
        scheduler = AsyncIOScheduler(timezone=cfg.timezone)
        hour, minute = map(int, cfg.daily_summary_time.split(":"))

        async def daily():
            await run_daily(p, cfg)

        async def weekly():
            await run_weekly(p, cfg)

        async def stale():
            await run_stale(p, cfg)

        async def retry():
            await p.retry_queue()

        scheduler.add_job(daily, "cron", hour=hour, minute=minute)
        scheduler.add_job(weekly, "cron", day_of_week="mon", hour=9)
        scheduler.add_job(stale, "cron", hour="10-19", minute=0)  # working hours only
        scheduler.add_job(retry, "interval", minutes=5)
        if pipeline is None:
            scheduler.start()
        yield
        if scheduler.running:
            scheduler.shutdown()

    app = FastAPI(title="Business automation kit", lifespan=lifespan)

    @app.get("/health")
    async def health():
        return {"status": "ok", "queued": len(app.state.pipeline.queued())}

    @app.post("/webhook/{source}")
    async def webhook(source: str, request: Request):
        limiter.check(request.client.host if request.client else "unknown")
        check_secret(request, cfg.webhook_secret)
        parser = SOURCES.get(source)
        if not parser:
            raise HTTPException(status_code=404, detail="unknown source")
        body = await read_limited_body(request, cfg.max_body_bytes)
        ctype = request.headers.get("content-type", "")
        try:
            if "json" in ctype:
                data = json.loads(body or b"{}")
            else:
                data = dict(parse_qsl(body.decode("utf-8", errors="replace")))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise HTTPException(status_code=422, detail="invalid body") from exc
        if not isinstance(data, dict):
            raise HTTPException(status_code=422, detail="expected an object")
        if source == "tilda" and is_test(data):
            return {"status": "ok"}  # Tilda connection check
        try:
            lead = parser(data, now(cfg))
        except ValidationError as exc:
            errors = [f"{'.'.join(map(str, e['loc'])) or 'lead'}: {e['msg']}" for e in exc.errors()]
            raise HTTPException(status_code=422, detail=errors) from exc
        status = await app.state.pipeline.process(lead)
        return {"status": status}

    return app


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)  # its INFO lines contain the bot token URL
app = create_app()
