from __future__ import annotations

import time

from fastapi.testclient import TestClient

from benjamin.apps.api import deps
from benjamin.apps.api.main import app


def _clear_dependency_caches() -> None:
    deps.get_memory_manager.cache_clear()
    deps.get_calendar_connector.cache_clear()
    deps.get_email_connector.cache_clear()
    deps.get_scheduler_service.cache_clear()
    deps.get_orchestrator.cache_clear()


def test_healthz_full_defaults(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BENJAMIN_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("BENJAMIN_AUTH_MODE", "off")
    monkeypatch.setenv("BENJAMIN_LLM_PROVIDER", "off")
    monkeypatch.setenv("BENJAMIN_GOOGLE_ENABLED", "off")

    _clear_dependency_caches()

    with TestClient(app) as client:
        response = client.get("/healthz/full")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["python"]["version"]
    assert payload["state_dir"]["path"] == str(tmp_path)
    assert payload["state_dir"]["writable"] is True
    assert payload["auth"] == {"mode": "off", "enabled": False}
    assert payload["llm"]["provider"] == "off"
    assert payload["llm"]["reachable"] is False
    assert set(payload["llm"]["features"].keys()) == {
        "planner",
        "summarizer",
        "drafter",
        "rule_builder",
        "retrieval",
    }
    assert payload["google"] == {
        "enabled": False,
        "token_present": False,
        "calendar_ready": False,
        "gmail_ready": False,
    }
    assert "rules_enabled" in payload["scheduler"]
    assert "daily_briefing_enabled" in payload["scheduler"]


def test_healthz_full_creates_state_dir_when_missing(tmp_path, monkeypatch) -> None:
    state_dir = tmp_path / "nested" / "state"
    monkeypatch.setenv("BENJAMIN_STATE_DIR", str(state_dir))
    monkeypatch.setenv("BENJAMIN_AUTH_MODE", "off")
    monkeypatch.setenv("BENJAMIN_LLM_PROVIDER", "off")
    monkeypatch.setenv("BENJAMIN_GOOGLE_ENABLED", "off")

    _clear_dependency_caches()

    with TestClient(app) as client:
        response = client.get("/healthz/full")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["state_dir"]["path"] == str(state_dir)
    assert payload["state_dir"]["writable"] is True
    assert state_dir.exists()


def test_healthz_full_vllm_unreachable_is_fast(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BENJAMIN_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("BENJAMIN_AUTH_MODE", "off")
    monkeypatch.setenv("BENJAMIN_GOOGLE_ENABLED", "off")
    monkeypatch.setenv("BENJAMIN_LLM_PROVIDER", "vllm")
    monkeypatch.setenv("BENJAMIN_VLLM_URL", "http://10.255.255.1:6553/v1/chat/completions")

    _clear_dependency_caches()

    with TestClient(app) as client:
        start = time.monotonic()
        response = client.get("/healthz/full")
        elapsed = time.monotonic() - start

    assert response.status_code == 200
    payload = response.json()
    assert payload["llm"]["provider"] == "vllm"
    assert payload["llm"]["reachable"] is False
    assert elapsed < 3.0
