from __future__ import annotations

from fastapi.testclient import TestClient

from benjamin.apps.api import deps
from benjamin.apps.api.main import app
from benjamin.core.cache.ttl import TTLCache


def _clear_dependency_caches() -> None:
    deps.get_memory_manager.cache_clear()
    deps.get_calendar_connector.cache_clear()
    deps.get_email_connector.cache_clear()
    deps.get_scheduler_service.cache_clear()
    deps.get_orchestrator.cache_clear()


def test_healthz_full_llm_ping_is_cached(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BENJAMIN_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("BENJAMIN_AUTH_MODE", "off")
    monkeypatch.setenv("BENJAMIN_GOOGLE_ENABLED", "off")
    monkeypatch.setenv("BENJAMIN_LLM_PROVIDER", "vllm")
    monkeypatch.setenv("BENJAMIN_VLLM_URL", "http://localhost:8001/v1/chat/completions")
    monkeypatch.setenv("BENJAMIN_PING_CACHE_TTL_S", "10")

    _clear_dependency_caches()

    calls = {"count": 0}

    def fake_ping(provider: str, timeout_s: float = 1.0) -> bool:
        assert provider == "vllm"
        calls["count"] += 1
        return True

    monkeypatch.setattr("benjamin.apps.api.main._HEALTH_PING_CACHE", TTLCache(default_ttl_s=10))
    monkeypatch.setattr("benjamin.apps.api.main._llm_reachable_uncached", fake_ping)

    with TestClient(app) as client:
        response_one = client.get("/healthz/full")
        response_two = client.get("/healthz/full")

    assert response_one.status_code == 200
    assert response_two.status_code == 200
    assert response_one.json()["llm"]["reachable"] is True
    assert response_two.json()["llm"]["reachable"] is True
    assert calls["count"] == 1
