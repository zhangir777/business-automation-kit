from typing import Protocol

from app.models import Lead


class Storage(Protocol):
    """Where leads are stored (Google Sheet or local xlsx)."""

    def append(self, lead: Lead) -> str:
        """Save the lead, return a link/reference to its row."""
        ...

    def records(self) -> list[dict]:
        """All rows as dicts keyed by COLUMNS (used by reports)."""
        ...


class Notifier(Protocol):
    async def send(self, text: str) -> None: ...
