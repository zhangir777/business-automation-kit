"""Tilda webhook: form-urlencoded fields named as in the form (Name, Phone, Email, ...),
plus formid, tranid, utm_* (if enabled). On connecting, Tilda sends `test=test` and expects 200."""

from datetime import datetime

from app.models import Lead

from .base import lead_from_dict


def is_test(data: dict) -> bool:
    return data.get("test") == "test"


def parse(data: dict, now: datetime) -> Lead:
    lead = lead_from_dict(data, "tilda", now)
    if data.get("formname"):
        lead.source = f"tilda: {data['formname']}"[:50]
    return lead
