"""Any website / CRM / landing builder that can POST JSON, e.g.
{"name": "...", "phone": "...", "email": "...", "comment": "...",
 "source": "...", "utm_source": "..."}"""

from datetime import datetime

from app.models import Lead

from .base import lead_from_dict


def parse(data: dict, now: datetime) -> Lead:
    source = str(data.get("source") or "website")[:50]
    return lead_from_dict(data, source, now)
