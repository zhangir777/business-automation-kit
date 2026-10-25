"""Source adapters turn an incoming payload into a Lead. Add a new source = add a function here
or a module and register it in SOURCES (app/sources/__init__.py)."""

from datetime import datetime

from app.models import Lead

ALIASES = {
    "name": ["name", "имя", "fio", "фио", "your name", "ваше имя", "client_name"],
    "phone": ["phone", "телефон", "tel", "phone_number", "номер телефона", "mobile"],
    "email": ["email", "e-mail", "почта", "mail"],
    "comment": [
        "comment",
        "comments",
        "комментарий",
        "message",
        "сообщение",
        "text",
        "вопрос",
        "textarea",
    ],
}
UTM_KEYS = ("utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term")


def pick(data: dict, field: str) -> str:
    lowered = {str(k).strip().lower(): v for k, v in data.items()}
    for alias in ALIASES[field]:
        value = lowered.get(alias)
        if isinstance(value, list):  # Google Forms namedValues: {"Имя": ["Аня"]}
            value = value[0] if value else ""
        if value not in (None, ""):
            return str(value)
    return ""


def lead_from_dict(data: dict, source: str, now: datetime) -> Lead:
    utm = {k: str(data[k]) for k in UTM_KEYS if data.get(k)}
    return Lead(
        name=pick(data, "name"),
        phone=pick(data, "phone") or None,
        email=pick(data, "email") or None,
        comment=pick(data, "comment"),
        source=source,
        utm=utm,
        created_at=now,
    )
