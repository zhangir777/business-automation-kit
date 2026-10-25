"""Google Forms via a tiny Apps Script trigger (see docs/TILDA_SETUP.md, section Google Forms):
UrlFetchApp.fetch(URL, {method: "post", contentType: "application/json",
                        payload: JSON.stringify(e.namedValues)})
namedValues looks like {"Имя": ["Аня"], "Телефон": ["8 777..."]}."""

from datetime import datetime

from app.models import Lead

from .base import lead_from_dict


def parse(data: dict, now: datetime) -> Lead:
    values = data.get("namedValues", data)
    return lead_from_dict(values, "google form", now)
