# Benjamin

A starter orchestration platform for agentic workflows.

## Layout

- `apps/api`: FastAPI service exposing chat + memory + jobs endpoints.
- `apps/worker`: background scheduler worker.
- `core`: orchestration, skills, scheduler, notifications, memory, model adapters, and observability.
- `infra`: local infra definitions and migrations.
- `tests`: unit tests for core behavior.

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
pytest
```

## Run services

```bash
uvicorn apps.api.main:app --reload
python -m apps.worker.worker
```

## Configuration

- `BENJAMIN_STATE_DIR`: directory for persisted state (`semantic.jsonl`, `episodic.jsonl`, `jobs.sqlite`).
- `BENJAMIN_MEMORY_AUTOWRITE`: automatic memory write policy switch (`on`/`off`, default `on`).
- `BENJAMIN_NOTIFIER`: enabled channels (`console`, `discord`, or comma-separated like `console,discord`; default `console`).
- `BENJAMIN_DISCORD_WEBHOOK_URL`: Discord webhook URL (required when `discord` notifier is enabled).
- `BENJAMIN_DAILY_BRIEFING_TIME`: default daily briefing time in local `HH:MM` format (default `09:00`).
- `BENJAMIN_TIMEZONE`: IANA timezone name used by scheduler cron jobs (default `America/New_York`).
- `BENJAMIN_TEST_MODE`: when set, scheduler uses in-memory storage and does not start worker threads.
- `BENJAMIN_APPROVALS_AUTOCLEAN`: approval retention policy (`on`/`off`, default `on`).
- `BENJAMIN_APPROVALS_TTL_HOURS`: pending approval time-to-live in hours (default `72`).

## Memory API examples

```bash
# List semantic facts
curl "http://localhost:8000/memory/semantic?scope=global"

# Explicitly teach a fact/preference
curl -X POST "http://localhost:8000/memory/semantic" \
  -H "Content-Type: application/json" \
  -d '{"key":"preference:editor","value":"Use vim keybindings","scope":"global","tags":["preference"]}'

# List last 20 episodic entries
curl "http://localhost:8000/memory/episodic?limit=20"
```

## Jobs API examples

```bash
# List scheduled jobs
curl "http://localhost:8000/jobs"

# Create a one-off reminder
curl -X POST "http://localhost:8000/jobs/reminder" \
  -H "Content-Type: application/json" \
  -d '{"message":"Submit expense report","run_at_iso":"2026-02-21T14:00:00+00:00"}'

# Enable/update daily briefing schedule
curl -X POST "http://localhost:8000/jobs/daily-briefing" \
  -H "Content-Type: application/json" \
  -d '{"time_hhmm":"09:00"}'

# Remove a job
curl -X DELETE "http://localhost:8000/jobs/daily-briefing"
```

## Approval workflow (API-only)

```bash
# 1) Trigger a write action through chat (returns "Approval required ...")
curl -X POST "http://localhost:8000/chat/" \
  -H "Content-Type: application/json" \
  -d '{"message":"reminders.create {\"message\":\"Submit expense report\",\"run_at_iso\":\"2026-02-21T14:00:00+00:00\"}"}'

# 2) List pending approvals
curl "http://localhost:8000/approvals?status=pending"

# 3a) Approve and execute the stored step
curl -X POST "http://localhost:8000/approvals/<APPROVAL_ID>/approve" \
  -H "Content-Type: application/json" \
  -d '{"approver_note":"Looks good"}'

# 3b) Or reject it
curl -X POST "http://localhost:8000/approvals/<APPROVAL_ID>/reject" \
  -H "Content-Type: application/json" \
  -d '{"reason":"Not needed anymore"}'
```
