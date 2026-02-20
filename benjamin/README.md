# BENJAMIN MVP

Initial vertical-slice MVP for **B**espoke **E**ngine for **N**atural **J**udgment, **A**utomation, **M**emory, **I**ntegrations & **N**otification.

## Features

- FastAPI `POST /chat` endpoint.
- Simple deterministic orchestrator (no LLM yet).
- Skill registry with one built-in skill: `filesystem.search_read`.
- Execution trace attached to each response.
- Unit tests for registry, orchestrator, and API endpoint.

## Setup

```bash
pip install -e .
```

## Run API

```bash
uvicorn apps.api.main:app --reload
```

## Run tests

```bash
pytest
```

## Example request

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"search banana","cwd":"."}'
```
