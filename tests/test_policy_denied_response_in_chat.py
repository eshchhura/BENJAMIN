from __future__ import annotations

from fastapi.testclient import TestClient

from benjamin.apps.api import deps
from benjamin.apps.api.main import app


def _reset_deps() -> None:
    deps.get_memory_manager.cache_clear()
    deps.get_scheduler_service.cache_clear()
    deps.get_orchestrator.cache_clear()
    deps.get_approval_store.cache_clear()
    deps.get_approval_service.cache_clear()


def test_chat_policy_denied_response_has_remediation(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BENJAMIN_TEST_MODE", "1")
    monkeypatch.setenv("BENJAMIN_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("BENJAMIN_SCOPE_MODE", "allowlist")
    monkeypatch.setenv("BENJAMIN_SCOPES_ENABLED", "")
    _reset_deps()

    with TestClient(app) as client:
        response = client.post("/chat/", json={"message": "reminders.create {\"message\":\"pay rent\",\"run_at_iso\":\"2030-01-01T10:00:00+00:00\"}"})
    assert response.status_code == 200
    text = response.json()["response"]
    assert "Policy denied" in text
    assert "reminders.write" in text
    assert "/ui/scopes" in text
