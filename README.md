# Benjamin

A starter orchestration platform for agentic workflows.

## Layout

- `src/benjamin/apps/api`: FastAPI service exposing chat + memory + jobs endpoints.
- `src/benjamin/apps/worker`: background scheduler worker.
- `src/benjamin/core`: orchestration, skills, scheduler, notifications, memory, model adapters, and observability.
- `infra`: local infra definitions and migrations.
- `tests`: unit tests for core behavior.

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
pytest

# Optional Google read-only integrations
pip install -e .[dev,google]
```

## Run services

```bash
benjamin-api
benjamin-worker
```

## Configuration

- `BENJAMIN_STATE_DIR`: directory for persisted state (`semantic.jsonl`, `episodic.jsonl`, `jobs.sqlite`).
- `BENJAMIN_MEMORY_AUTOWRITE`: automatic memory write policy switch (`on`/`off`, default `on`).
- `BENJAMIN_NOTIFIER`: enabled channels (`console`, `discord`, or comma-separated like `console,discord`; default `console`).
- `BENJAMIN_DISCORD_WEBHOOK_URL`: Discord webhook URL (required when `discord` notifier is enabled).
- `BENJAMIN_DAILY_BRIEFING_TIME`: default daily briefing time in local `HH:MM` format (default `09:00`).
- `BENJAMIN_TIMEZONE`: IANA timezone name used by scheduler cron jobs (default `America/New_York`).
- `BENJAMIN_GOOGLE_ENABLED`: enable Google calendar/gmail read integrations (`on`/`off`, default `off`).
- `BENJAMIN_GOOGLE_TOKEN_PATH`: OAuth token JSON path (default `<BENJAMIN_STATE_DIR>/google_token.json`).
- `BENJAMIN_GOOGLE_CREDENTIALS_PATH`: optional OAuth client secrets path (used only for external token bootstrap tooling).
- `BENJAMIN_GMAIL_QUERY_IMPORTANT`: default Gmail query for briefing email section.
- `BENJAMIN_CALENDAR_ID`: default calendar id for reads and event creation (default `primary`).
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


Write skills (approval-gated):
- `calendar.create_event`: create a Google Calendar event.
- `gmail.draft_email`: create a Gmail draft (no send).

## Approval workflow (API-only)

```bash
# 1) Trigger a write action through chat (returns "Approval required ...")
curl -X POST "http://localhost:8000/chat/"   -H "Content-Type: application/json"   -d '{"message":"calendar.create_event {\"title\":\"Design review\",\"start_iso\":\"2026-02-21T14:00:00-05:00\",\"end_iso\":\"2026-02-21T14:30:00-05:00\"}"}'

# Alternate write skill (also approval-gated)
curl -X POST "http://localhost:8000/chat/"   -H "Content-Type: application/json"   -d '{"message":"gmail.draft_email {\"to\":[\"alex@example.com\"],\"subject\":\"Status update\",\"body\":\"Drafting the weekly status update.\"}"}'

# 2) List pending approvals
curl "http://localhost:8000/approvals?status=pending"

# 3a) Approve and execute the stored step
curl -X POST "http://localhost:8000/approvals/<APPROVAL_ID>/approve"   -H "Content-Type: application/json"   -d '{"approver_note":"Looks good"}'

# 3b) Or reject it
curl -X POST "http://localhost:8000/approvals/<APPROVAL_ID>/reject"   -H "Content-Type: application/json"   -d '{"reason":"Not needed anymore"}'

# 4) Inspect approval record to see stored execution result/error
curl "http://localhost:8000/approvals"
```

## Integrations status

```bash
curl "http://localhost:8000/integrations/status"
```

When Google integrations are configured (`BENJAMIN_GOOGLE_ENABLED=on` and token file present), daily briefing includes:
- Today's schedule (next 12 hours, up to 5 events).
- Important emails (query from `BENJAMIN_GMAIL_QUERY_IMPORTANT`, up to 5 threads).

If unavailable, briefing remains memory-only.
