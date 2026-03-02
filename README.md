# Benjamin

A starter orchestration platform for agentic workflows.

## Layout

- `src/benjamin/apps/api`: FastAPI service exposing chat + memory + jobs + approvals + rules endpoints plus a Jinja2/HTMX Command Center at `/ui`.
- `src/benjamin/apps/worker`: background scheduler worker.
- `src/benjamin/core`: orchestration, skills, scheduler, notifications, memory, model adapters, and observability.
- `infra`: local infra definitions and migrations.
- `tests`: unit tests for core behavior.

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
python scripts/test.py

# Optional Google read-only integrations
pip install -e .[dev,google]
```


## Runbook

See the operational runbook for one-command dev startup, environment checks, and troubleshooting: [`docs/RUNBOOK.md`](docs/RUNBOOK.md).

## Development workflow

Always install the project in editable mode before running tests so imports resolve from the package metadata (no `PYTHONPATH` needed):

```bash
python -m pip install -e .[dev]
python -m pytest -q
```

Preferred test command:

```bash
python scripts/test.py
```


## Ops Doctor

Validate persisted BENJAMIN state (JSON/JSONL), detect corruption, and optionally repair/compact files:

```bash
python scripts/doctor.py
python scripts/doctor.py --repair
python scripts/doctor.py --compact
```

Safety guarantees:
- Read-only by default.
- `--repair` / `--compact` always create backups like `<file>.bak.<timestamp>`.
- Rewrites are atomic (temp file then replace).

## Run services

```bash
benjamin-api
benjamin-worker
```

## Configuration

- `BENJAMIN_STATE_DIR`: directory for persisted state (`semantic.jsonl`, `episodic.jsonl`, `tasks.jsonl`, `jobs.sqlite`).
- `BENJAMIN_LEDGER_MAX`: max retained execution ledger entries in `executions.jsonl` (default `5000`).
- `BENJAMIN_LEDGER_LOCK_MODE`: execution ledger lock mode (`file`/`off`, default `file`).
- `BENJAMIN_TASKS_MAX`: max retained chat task run records in `tasks.jsonl` (default `500`).
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
- `BENJAMIN_RULES_ENABLED`: enable periodic rules evaluator (`on`/`off`, default `off`).
- `BENJAMIN_RULES_EVERY_MINUTES`: interval for evaluator job (default `5`).
- `BENJAMIN_SCOPE_MODE`: permissions scope mode (`default`/`allowlist`, default `default`).
- `BENJAMIN_SCOPES_ENABLED`: comma-separated scope list used as write allowlist in `default` mode or strict allowlist in `allowlist` mode.
- `BENJAMIN_RULES_ALLOWED_SCOPES`: comma-separated scope list rules are allowed to propose (default `reminders.write`).
- `BENJAMIN_POLICY_OVERRIDES`: when `on` (default), UI/API policy changes are stored in `<BENJAMIN_STATE_DIR>/policy_overrides.json`; when `off`, scopes are read-only from env.
- `BENJAMIN_AUTH_MODE`: API/UI auth mode (`off`/`token`, default `token`).
- `BENJAMIN_AUTH_TOKEN`: required shared token when `BENJAMIN_AUTH_MODE=token`.
- `BENJAMIN_EXPOSE_PUBLIC`: when `on`, `/chat` POST also requires auth token (default `off`).
- `BENJAMIN_HTTP_TIMEOUT_S`: default total HTTP timeout in seconds for resilient HTTP calls (default `10`).
- `BENJAMIN_HTTP_RETRIES`: shared HTTP retry count for timeout/connection/429/5xx (default `2`).
- `BENJAMIN_HTTP_BACKOFF_BASE_MS`: base exponential backoff in milliseconds (default `250`).
- `BENJAMIN_BREAKERS_ENABLED`: circuit breaker switch (`on`/`off`, default `on`).
- `BENJAMIN_BREAKER_FAILURE_THRESHOLD`: consecutive failures before opening breaker (default `3`).
- `BENJAMIN_BREAKER_OPEN_SECONDS`: open-state cooldown before half-open trial (default `60`).
- `BENJAMIN_BREAKER_HALFOPEN_MAX_TRIALS`: trial requests allowed while half-open (default `1`).
- `BENJAMIN_HTTP_USER_AGENT`: shared HTTP `User-Agent` header value (default `BENJAMIN/1.0`).
- `BENJAMIN_PING_CACHE_TTL_S`: TTL in seconds for cached `/healthz/full` LLM reachability pings (default `10`).
- `BENJAMIN_LOG_LEVEL`: structured app log level (`DEBUG`/`INFO`/`WARNING`/`ERROR`, default `INFO`).
- `BENJAMIN_LOG_TO_FILE`: enable rotating log file output (`on`/`off`, default `on`).
- `BENJAMIN_LOG_DIR`: optional log directory override (default `<BENJAMIN_STATE_DIR>/logs`).
- `BENJAMIN_LOG_MAX_BYTES`: rotating log file max size in bytes (default `5000000`).
- `BENJAMIN_LOG_BACKUP_COUNT`: rotating log backup count (default `5`).

Logs are emitted as JSONL to stdout and (by default) to `<BENJAMIN_STATE_DIR>/logs/benjamin.log` with rotation.

Circuit breakers are maintained per service (`llm`, `gmail`, `calendar`) and persisted in `<BENJAMIN_STATE_DIR>/breakers.json`. Delete that file to reset breaker state manually.

When auth mode is `token`, pass the token using either:
- HTTP header: `X-BENJAMIN-TOKEN: <token>`
- Cookie: `benjamin_token=<token>` (set by `/ui/login`)

## Policy & Permissions v2

Canonical scopes:

- Read scopes (enabled by default in `default` mode): `filesystem.read`, `web.read`, `calendar.read`, `gmail.read`, `memory.read`, `rules.read`, `jobs.read`.
- Write scopes (disabled by default): `reminders.write`, `calendar.write`, `gmail.draft`, `gmail.send`, `memory.write`, `rules.write`, `jobs.write`.

Mode behavior:

- `BENJAMIN_SCOPE_MODE=default`:
  - all read scopes enabled automatically;
  - write scopes enabled only when listed in `BENJAMIN_SCOPES_ENABLED`.
- `BENJAMIN_SCOPE_MODE=allowlist`:
  - only scopes listed in `BENJAMIN_SCOPES_ENABLED` are enabled.

Rules constraints:

- Rules `propose_step` actions are additionally constrained by `BENJAMIN_RULES_ALLOWED_SCOPES`.
- Default rules allowlist is `reminders.write` only.

Example: enable calendar event creation + Gmail drafts, while keeping Gmail send disabled:

```bash
export BENJAMIN_SCOPE_MODE=default
export BENJAMIN_SCOPES_ENABLED="calendar.write,gmail.draft"
# Deliberately omit gmail.send
```

Overrides & management:

- Open `/ui/scopes` for interactive toggles.
- API reads current snapshot at `GET /v1/security/scopes`.
- API writes mutate only `<BENJAMIN_STATE_DIR>/policy_overrides.json` (env is unchanged).

```bash
# Enable scopes
curl -X POST "http://localhost:8000/v1/security/scopes/enable"   -H "Content-Type: application/json"   -H "X-BENJAMIN-TOKEN: ${BENJAMIN_AUTH_TOKEN}"   -d '{"scopes":["calendar.write","gmail.draft"]}'

# Disable scope
curl -X POST "http://localhost:8000/v1/security/scopes/disable"   -H "Content-Type: application/json"   -H "X-BENJAMIN-TOKEN: ${BENJAMIN_AUTH_TOKEN}"   -d '{"scopes":["gmail.draft"]}'

# Set rules propose_step allowlist
curl -X POST "http://localhost:8000/v1/security/rules/allowed-scopes"   -H "Content-Type: application/json"   -H "X-BENJAMIN-TOKEN: ${BENJAMIN_AUTH_TOKEN}"   -d '{"scopes":["reminders.write","calendar.write"]}'

# Reset rules allowlist to defaults
curl -X POST "http://localhost:8000/v1/security/rules/allowed-scopes/reset"   -H "X-BENJAMIN-TOKEN: ${BENJAMIN_AUTH_TOKEN}"
```

Policy telemetry:

- Policy allow/deny decisions are written to episodic memory with `kind="policy"`.
- View them in `/ui/runs` (kind filter `policy`) and in `/ui/correlation/{correlation_id}`.


## Memory API examples

```bash
# List semantic facts
curl "http://localhost:8000/memory/semantic?scope=global"

# Explicitly teach a fact/preference
curl -X POST "http://localhost:8000/memory/semantic" \
  -H "Content-Type: application/json" \
  -H "X-BENJAMIN-TOKEN: ${BENJAMIN_AUTH_TOKEN}" \
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
  -H "X-BENJAMIN-TOKEN: ${BENJAMIN_AUTH_TOKEN}" \
  -d '{"message":"Submit expense report","run_at_iso":"2026-02-21T14:00:00+00:00"}'

# Enable/update daily briefing schedule
curl -X POST "http://localhost:8000/jobs/daily-briefing" \
  -H "Content-Type: application/json" \
  -H "X-BENJAMIN-TOKEN: ${BENJAMIN_AUTH_TOKEN}" \
  -d '{"time_hhmm":"09:00"}'

# Remove a job
curl -X DELETE "http://localhost:8000/jobs/daily-briefing" \
  -H "X-BENJAMIN-TOKEN: ${BENJAMIN_AUTH_TOKEN}"
```


Write skills (approval-gated):
- `calendar.create_event`: create a Google Calendar event.
- `gmail.draft_email`: create a Gmail draft (no send).

## Plan Critic

Before execution or approval creation, BENJAMIN runs a deterministic plan critic that validates and normalizes write-action arguments. If required details are missing or contradictory, it asks a clarification question instead of creating approvals or executing steps.

## Idempotency and replay safety

BENJAMIN writes an append-only execution ledger at `<BENJAMIN_STATE_DIR>/executions.jsonl` for side-effecting paths.

- Approval execution uses a stable key (`approval_id + skill_name + canonical args`) so repeated approve calls do not execute write tools twice.
- Scheduler jobs (reminders, daily briefing, rules evaluator) use job-run keys to best-effort skip duplicate notification sends in repeated invocations.
- Rule `propose_step` actions use rule-action keys (`rule_id + action index + matched item + action signature`) to avoid duplicate approval creation across retries/restarts.

Read-only deterministic work can still run; the ledger is focused on preventing duplicate side effects.

## Approval workflow (API-only)

```bash
# 1) Trigger a write action through chat (returns "Approval required ...")
curl -X POST "http://localhost:8000/chat/"   -H "Content-Type: application/json"   -d '{"message":"calendar.create_event {\"title\":\"Design review\",\"start_iso\":\"2026-02-21T14:00:00-05:00\",\"end_iso\":\"2026-02-21T14:30:00-05:00\"}"}'

# Alternate write skill (also approval-gated)
curl -X POST "http://localhost:8000/chat/"   -H "Content-Type: application/json"   -d '{"message":"gmail.draft_email {\"to\":[\"alex@example.com\"],\"subject\":\"Status update\",\"body\":\"Drafting the weekly status update.\"}"}'

# 2) List pending approvals
curl "http://localhost:8000/approvals?status=pending"

# 3a) Approve and execute the stored step
curl -X POST "http://localhost:8000/approvals/<APPROVAL_ID>/approve" \
  -H "Content-Type: application/json" \
  -H "X-BENJAMIN-TOKEN: ${BENJAMIN_AUTH_TOKEN}" \
  -d '{"approver_note":"Looks good"}'

# 3b) Or reject it
curl -X POST "http://localhost:8000/approvals/<APPROVAL_ID>/reject" \
  -H "Content-Type: application/json" \
  -H "X-BENJAMIN-TOKEN: ${BENJAMIN_AUTH_TOKEN}" \
  -d '{"reason":"Not needed anymore"}'

# 4) Inspect approval record to see stored execution result/error
curl "http://localhost:8000/approvals"
```

`/healthz/full` uses a short-timeout shared HTTP check against `.../v1/models` and caches LLM reachability for `BENJAMIN_PING_CACHE_TTL_S` seconds to keep endpoint latency stable.

## Integrations status

`/healthz/full` performs a short-timeout OpenAI-compatible reachability check (`.../v1/models`) through the shared HTTP client and caches ping results for `BENJAMIN_PING_CACHE_TTL_S` seconds. Both `/healthz/full` and `/integrations/status` include breaker snapshots so degraded services are visible in API and UI.

```bash
curl "http://localhost:8000/integrations/status"
```

When Google integrations are configured (`BENJAMIN_GOOGLE_ENABLED=on` and token file present), daily briefing includes:
- Today's schedule (next 12 hours, up to 5 events).
- Important emails (query from `BENJAMIN_GMAIL_QUERY_IMPORTANT`, up to 5 threads).

If unavailable, briefing remains memory-only.

## Rules API examples

Rules are deterministic and stateful. Each evaluation only considers **new** trigger items since the previous run by combining a timestamp cursor (`state.last_cursor_iso`) and dedupe IDs (`state.seen_ids`). This prevents duplicate notifications and repeated approval proposals across periodic evaluations and restarts.

`cooldown_minutes` blocks repeated firing after a successful match, and `max_actions_per_run` caps how many actions execute in one evaluation pass.

```bash
# List all rules
curl "http://localhost:8000/rules"

# Create deterministic gmail rule with notify action, cooldown, and action cap
curl -X POST "http://localhost:8000/rules" \
  -H "Content-Type: application/json" \
  -H "X-BENJAMIN-TOKEN: ${BENJAMIN_AUTH_TOKEN}" \
  -d '{"name":"important inbox","trigger":{"type":"gmail","query":"label:inbox newer_than:1d","max_results":5},"condition":{"contains":"invoice"},"actions":[{"type":"notify","title":"Inbox rule","body_template":"Matched {{count}} items top={{top1}} at {{now_iso}}"}],"cooldown_minutes":30,"max_actions_per_run":1}'

# Evaluate enabled rules immediately
curl -X POST "http://localhost:8000/rules/evaluate-now" \
  -H "X-BENJAMIN-TOKEN: ${BENJAMIN_AUTH_TOKEN}"

# Reset a rule's evaluation state (cursor, seen IDs, cooldown, run/match timestamps)
curl -X POST "http://localhost:8000/rules/<RULE_ID>/reset-state" \
  -H "X-BENJAMIN-TOKEN: ${BENJAMIN_AUTH_TOKEN}"

# Dry-run test an existing rule without side effects
curl -X POST "http://localhost:8000/rules/<RULE_ID>/test" \
  -H "X-BENJAMIN-TOKEN: ${BENJAMIN_AUTH_TOKEN}"

# Dry-run test a transient draft rule without saving it
curl -X POST "http://localhost:8000/rules/test" \
  -H "Content-Type: application/json" \
  -H "X-BENJAMIN-TOKEN: ${BENJAMIN_AUTH_TOKEN}" \
  -d '{"name":"draft inbox","trigger":{"type":"gmail","query":"label:inbox","max_results":5},"condition":{"contains":"invoice"},"actions":[{"type":"notify","title":"Preview","body_template":"Matched {{count}} top={{top1}}"}]}'
```

## Testing Rules (Dry-Run)

Use rule test mode when you want to verify matching behavior and action outputs safely.

- UI:
  - On `/ui/rules`, click **Test** on any existing rule row to render a match/action preview inline.
  - In the create form, click **Test Draft** to preview the current draft without saving.
- API:
  - `POST /rules/{id}/test` previews an existing persisted rule.
  - `POST /rules/test` previews a transient `RuleCreate` payload.

Dry-run preview fetches trigger items and evaluates conditions exactly like normal execution, but it does **not** send notifications, create approvals, write to ledger, mutate rule state, or append episodic memory entries.

## Command Center UI

Open `http://localhost:8000/ui` to use the web UI for chat, approvals, jobs, rules, memory management, and run history.

Run history dashboard and drilldowns:
- `/ui/runs`: run history with filters via `kind=chat|rule|job|approval|all`, `status=ok|failed|skipped|all`, `q=<text>`, and `limit=<1..200>`.
- `/ui/runs/chat/{task_id}`: full plan/steps/trace for a chat run.
- `/ui/runs/rules/{rule_id}`: rule definition plus recent episodes.
- `/ui/runs/approvals/{approval_id}`: approval record detail including idempotency key and ledger timeline.
- `/ui/correlation/{correlation_id}`: correlation-centric view linking tasks, episodes, ledger records, and approvals.
- `/runs/search`: JSON search endpoint for debugging and future UI integrations.

## Local GLM-4.7 (vLLM, single GPU)

Run vLLM outside BENJAMIN (optional separate venv):

```bash
pip install vllm
vllm serve zai-org/GLM-4.7 \
  --host 127.0.0.1 --port 8001 \
  --dtype auto \
  --max-model-len 8192 \
  --gpu-memory-utilization 0.90
```

If you hit OOM, reduce `--max-model-len`, lower `--gpu-memory-utilization`, or use quantization supported by your setup.

BENJAMIN environment:

```bash
export BENJAMIN_LLM_PROVIDER=vllm
export BENJAMIN_LLM_MODEL=zai-org/GLM-4.7
export BENJAMIN_VLLM_URL=http://127.0.0.1:8001/v1/chat/completions
export BENJAMIN_LLM_TEMPERATURE=0.2
export BENJAMIN_LLM_TIMEOUT_S=45

export BENJAMIN_LLM_PLANNER=on
export BENJAMIN_LLM_SUMMARIZER=on
export BENJAMIN_LLM_DRAFTER=on
export BENJAMIN_LLM_RULE_BUILDER=on
export BENJAMIN_LLM_RETRIEVAL=on

export BENJAMIN_LLM_STRICT_JSON=on
export BENJAMIN_LLM_MAX_TOKENS_JSON=1200
export BENJAMIN_LLM_MAX_TOKENS_TEXT=800
```

Set `BENJAMIN_LLM_PROVIDER=off` to keep fully deterministic behavior.
