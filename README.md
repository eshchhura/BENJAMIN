# Benjamin

A starter orchestration platform for agentic workflows.

## Layout

- `apps/api`: FastAPI service exposing chat + task endpoints.
- `apps/worker`: background worker and scheduler loop.
- `core`: orchestration, skills, memory, model adapters, and observability.
- `infra`: local infra definitions and migrations.
- `tests`: unit tests for core behavior.

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
pytest
```

## Memory configuration

Benjamin persists memory in JSONL files under a state directory:

- `BENJAMIN_STATE_DIR`: directory for persisted state.
  - Default: `~/.benjamin` (Unix) or `%USERPROFILE%\\.benjamin` (Windows).
- `BENJAMIN_MEMORY_AUTOWRITE`: automatic write policy switch (`on` or `off`, default `on`).

Memory files in the state directory:

- `semantic.jsonl`
- `episodic.jsonl`

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
