from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    webhook_secret: str = "change-me"
    timezone: str = "Asia/Almaty"

    # Google Sheets (empty = demo mode: local data/leads.xlsx)
    google_credentials_file: Path = ROOT / "secrets" / "google-service-account.json"
    google_sheet_id: str = ""
    google_worksheet: str = "Leads"
    sheet_language: str = "ru"  # header and status labels: ru or en

    # Telegram (empty = notifications are printed to the log)
    telegram_bot_token: str = ""
    telegram_chat_ids: list[int] = []

    # Email for the weekly report (optional)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    report_email_to: str = ""

    data_dir: Path = ROOT / "data"
    dedupe_minutes: int = 10
    stale_hours: int = 2
    daily_summary_time: str = "19:00"
    max_body_bytes: int = 64_000
    rate_limit_per_minute: int = 30

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @property
    def google_enabled(self) -> bool:
        return bool(self.google_sheet_id) and self.google_credentials_file.exists()


settings = Settings()
