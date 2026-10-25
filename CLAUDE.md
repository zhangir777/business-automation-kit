# business-automation-kit

## Commands
- `uv sync`, `uv run pytest -q`, `uv run ruff format . && uv run ruff check --fix .`
- Run: `uv run uvicorn app.main:app --port 8000`; test lead: `uv run python scripts/send_test_lead.py`

## Architecture
source adapter (`app/sources/`) → `Lead` (`app/models.py`) → `Pipeline` (`app/pipeline.py`) → storage + notifier (`app/sinks/`).
Jobs (`app/jobs/reports.py`) are pure functions over `storage.records()`; scheduling lives in `app/main.py`.

## Rules
- Demo mode must keep working without any keys (local xlsx + log notifier).
- Secrets: `.env` and `secrets/` only. Never log URLs with the bot token, never print keys, never ask to paste keys in chat.
- Never lose a lead: storage errors → queue; keep `retry_queue` idempotent.
- Times: naive datetimes in `settings.timezone` (Asia/Almaty).
- Tests are offline: use in-memory storage/notifier fakes (see tests).
