import re
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

STATUSES = ["Новая", "В работе", "Закрыта", "Спам"]
COLUMNS = [
    "Дата",
    "Имя",
    "Телефон",
    "Источник",
    "Комментарий",
    "Статус",
    "Ответственный",
    "Email",
    "UTM",
]


def normalize_phone(raw: str | None) -> str | None:
    """KZ/RU numbers to +7XXXXXXXXXX: '8 777 123 45 67', '+7 (777) 123-45-67', '7771234567'.
    Other international numbers (+...) are kept as +digits. Returns None if not a phone."""
    if not raw:
        return None
    raw = raw.strip()
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 11 and digits[0] in "78":
        return "+7" + digits[1:]
    if len(digits) == 10 and digits[0] in "67":  # KZ mobile 7xx, KZ/RU landline-ish 6xx/7xx
        return "+7" + digits
    if raw.startswith("+") and 8 <= len(digits) <= 15:
        return "+" + digits
    return None


class Lead(BaseModel):
    name: str = Field(default="", max_length=200)
    phone: str | None = None
    email: EmailStr | None = None
    source: str = Field(default="website", max_length=50)
    comment: str = Field(default="", max_length=2000)
    utm: dict[str, str] = {}
    created_at: datetime
    status: str = "Новая"
    manager: str = ""

    @field_validator("name", "comment", "source", mode="before")
    @classmethod
    def strip(cls, v):
        return (v or "").strip() if isinstance(v, str | type(None)) else v

    @field_validator("email", mode="before")
    @classmethod
    def empty_email(cls, v):
        return v.strip() if isinstance(v, str) and v.strip() else None

    @field_validator("phone", mode="before")
    @classmethod
    def check_phone(cls, v):
        if v in (None, ""):
            return None
        normalized = normalize_phone(str(v))
        if not normalized:
            raise ValueError("invalid phone number")
        return normalized

    @model_validator(mode="after")
    def contact_required(self):
        if not self.phone and not self.email:
            raise ValueError("phone or email is required")
        return self

    def row(self) -> list[str]:
        utm = " ".join(f"{k}={v}" for k, v in self.utm.items())
        return [
            self.created_at.strftime("%Y-%m-%d %H:%M"),
            self.name,
            self.phone or "",
            self.source,
            self.comment,
            self.status,
            self.manager,
            self.email or "",
            utm,
        ]
