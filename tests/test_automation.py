from datetime import date, datetime, timedelta
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from app.config import Settings
from app.jobs.reports import daily_summary, stale_leads, weekly_report
from app.main import create_app
from app.models import COLUMNS, Lead, normalize_phone
from app.pipeline import Pipeline
from app.sinks.local_xlsx import LocalXlsx
from app.sources import generic_json, google_form, tilda

NOW = datetime(2026, 11, 2, 12, 0)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("8 777 123 45 67", "+77771234567"),
        ("+7 (777) 123-45-67", "+77771234567"),
        ("87771234567", "+77771234567"),
        ("77771234567", "+77771234567"),
        ("7771234567", "+77771234567"),
        ("8-701-555-66-77", "+77015556677"),
        ("+7 727 222 33 44", "+77272223344"),
        ("8 (916) 123-45-67", "+79161234567"),
        ("+998 90 123 45 67", "+998901234567"),
        ("12345", None),
        ("", None),
        ("abc", None),
        ("8 777 123 45", None),
    ],
)
def test_normalize_phone(raw, expected):
    assert normalize_phone(raw) == expected


def test_tilda_payload():
    lead = tilda.parse(
        {"Name": "Аня", "Phone": "8 777 123 45 67", "Comments": "Цена?", "formname": "Заявка",
         "utm_source": "instagram", "tranid": "123"}, NOW,
    )  # fmt: skip
    assert (lead.name, lead.phone, lead.comment) == ("Аня", "+77771234567", "Цена?")
    assert lead.source == "tilda: Заявка" and lead.utm == {"utm_source": "instagram"}


def test_generic_json_and_google_form():
    lead = generic_json.parse({"name": "Bob", "email": "b@x.com", "source": "landing"}, NOW)
    assert lead.email == "b@x.com" and lead.source == "landing"
    lead = google_form.parse({"namedValues": {"Имя": ["Дана"], "Телефон": ["87001112233"]}}, NOW)
    assert lead.phone == "+77001112233" and lead.source == "google form"


@pytest.mark.parametrize(
    "payload",
    [{"name": "No contact"}, {"phone": "123"}, {"email": "not-an-email"}],
)
def test_invalid_leads(payload):
    with pytest.raises(ValueError):
        generic_json.parse(payload, NOW)


class MemoryStorage:
    def __init__(self, fail=False):
        self.rows, self.fail = [], fail

    def append(self, lead):
        if self.fail:
            raise ConnectionError("sheet down")
        self.rows.append(lead)
        return f"row {len(self.rows) + 1}"

    def records(self):
        return [dict(zip(COLUMNS, lead.row(), strict=True)) for lead in self.rows]


class MemoryNotifier:
    def __init__(self):
        self.messages = []

    async def send(self, text):
        self.messages.append(text)


def make_pipeline(tmp_path, fail=False):
    return Pipeline(MemoryStorage(fail), MemoryNotifier(), tmp_path / "queue.jsonl")


def lead(minutes=0, **kw):
    data = {"name": "A", "phone": "87771234567", "comment": "hi"} | kw
    return Lead(**data, created_at=NOW + timedelta(minutes=minutes))


async def test_pipeline_saves_and_notifies(tmp_path):
    p = make_pipeline(tmp_path)
    assert await p.process(lead()) == "saved"
    assert len(p.storage.rows) == 1
    msg = p.notifier.messages[0]
    assert 'href="tel:+77771234567"' in msg and "row 2" in msg


async def test_dedupe_within_10_minutes(tmp_path):
    p = make_pipeline(tmp_path)
    assert await p.process(lead(0)) == "saved"
    assert await p.process(lead(5)) == "duplicate"
    assert await p.process(lead(16)) == "saved"  # 16 min after the last seen copy
    assert await p.process(lead(17, comment="other")) == "saved"
    assert len(p.storage.rows) == 3


async def test_sheet_down_queues_and_retries(tmp_path):
    p = make_pipeline(tmp_path, fail=True)
    assert await p.process(lead()) == "queued"
    assert len(p.queued()) == 1
    assert any("unavailable" in m for m in p.notifier.messages)
    assert await p.retry_queue() == 0  # still down
    p.storage.fail = False
    assert await p.retry_queue() == 1
    assert p.queued() == [] and len(p.storage.rows) == 1


def records():
    rows = [
        lead(source="tilda"),
        lead(30, phone="87770000001", source="tilda", status="В работе"),
        lead(60, phone="87770000002", source="instagram"),
        lead(-60 * 24, phone="87770000003", source="tilda"),  # yesterday
    ]
    return [dict(zip(COLUMNS, r.row(), strict=True)) for r in rows]


def test_daily_summary_numbers():
    text = daily_summary(records(), date(2026, 11, 2))
    assert "Leads today: 3" in text
    assert "tilda: 2" in text and "instagram: 1" in text
    assert "all time: 3" in text  # 3 with status Новая


def test_stale_leads():
    # at 14:30 with a 2 h limit: 12:00 (Новая) and yesterday's are stale; 12:30 is "В работе";
    # 13:00 is too fresh
    stale = stale_leads(records(), datetime(2026, 11, 2, 14, 30), 2)
    assert sorted(r["Телефон"] for r in stale) == ["+77770000003", "+77771234567"]


def test_weekly_report():
    content, stats = weekly_report(records(), date(2026, 11, 2))
    assert stats["total"] == 4
    assert stats["per_day"]["2026-11-02"] == 3 and stats["per_day"]["2026-11-01"] == 1
    wb = load_workbook(BytesIO(content))
    assert wb.sheetnames == ["Summary", "Leads"] and wb["Summary"]._charts
    assert wb["Leads"].max_row == 5


def test_local_xlsx_storage(tmp_path):
    store = LocalXlsx(tmp_path / "leads.xlsx")
    assert store.append(lead()) == "leads.xlsx, row 2"
    ws = load_workbook(tmp_path / "leads.xlsx").active
    assert [c.value for c in ws[1]] == COLUMNS and ws.freeze_panes == "A2"
    assert ws.data_validations.dataValidation[0].formula1.startswith('"Новая')
    assert store.records()[0]["Телефон"] == "+77771234567"


def test_english_sheet_keeps_internal_keys(tmp_path):
    store = LocalXlsx(tmp_path / "leads.xlsx", lang="en")
    store.append(lead())
    ws = load_workbook(tmp_path / "leads.xlsx").active
    assert [c.value for c in ws[1]][:3] == ["Date", "Name", "Phone"]
    assert ws["F2"].value == "New"
    record = store.records()[0]
    assert record["Телефон"] == "+77771234567" and record["Статус"] == "New"
    assert "all time: 1" in daily_summary([record], date(2000, 1, 1))  # "New" counts as open


@pytest.fixture
def client(tmp_path):
    cfg = Settings(webhook_secret="s3cret", data_dir=tmp_path, rate_limit_per_minute=5,
                   max_body_bytes=2000, _env_file=None)  # fmt: skip
    p = make_pipeline(tmp_path)
    with TestClient(create_app(cfg, p)) as c:
        c.pipeline = p
        yield c


def test_webhook_requires_secret(client):
    body = {"name": "A", "phone": "87771234567"}
    assert client.post("/webhook/json", json=body).status_code == 401
    assert client.post("/webhook/json?secret=wrong", json=body).status_code == 401
    r = client.post("/webhook/json", json=body, headers={"X-Webhook-Secret": "s3cret"})
    assert r.status_code == 200 and r.json() == {"status": "saved"}


def test_webhook_tilda_form_and_test_ping(client):
    r = client.post("/webhook/tilda?secret=s3cret", data={"test": "test"})
    assert r.json() == {"status": "ok"} and client.pipeline.storage.rows == []
    r = client.post("/webhook/tilda?secret=s3cret", data={"Name": "Аня", "Phone": "+7 777 1112233"})
    assert r.json() == {"status": "saved"}


def test_webhook_validation_and_limits(client):
    h = {"X-Webhook-Secret": "s3cret"}
    assert client.post("/webhook/json", json={"name": "x"}, headers=h).status_code == 422
    assert client.post("/webhook/unknown", json={}, headers=h).status_code == 404
    big = {"comment": "x" * 5000, "phone": "87771234567"}
    assert client.post("/webhook/json", json=big, headers=h).status_code == 413
    codes = [client.get("/health").status_code] + [
        client.post("/webhook/json", json={"phone": "87771234567"}, headers=h).status_code
        for _ in range(5)
    ]
    assert codes[0] == 200 and 429 in codes  # rate limit: 5/min


def test_timezone_default():
    cfg = Settings(_env_file=None)
    assert cfg.timezone == "Asia/Almaty" and str(cfg.tz) == "Asia/Almaty"
