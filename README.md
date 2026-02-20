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
