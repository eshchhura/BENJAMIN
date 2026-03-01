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
    deps.get_calendar_connector.cache_clear()
    deps.get_email_connector.cache_clear()
    deps.get_notification_router.cache_clear()


def test_ui_redirects_to_login_when_unauthenticated(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BENJAMIN_TEST_MODE", "1")
    monkeypatch.setenv("BENJAMIN_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("BENJAMIN_AUTH_MODE", "token")
    monkeypatch.setenv("BENJAMIN_AUTH_TOKEN", "secret-token")
    _reset_deps()

    with TestClient(app) as client:
        response = client.get("/ui/chat", follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["location"] == "/ui/login"


def test_rules_post_unauthorized_without_token(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BENJAMIN_TEST_MODE", "1")
    monkeypatch.setenv("BENJAMIN_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("BENJAMIN_AUTH_MODE", "token")
    monkeypatch.setenv("BENJAMIN_AUTH_TOKEN", "secret-token")
    _reset_deps()

    with TestClient(app) as client:
        response = client.post("/rules", json={"name": "blocked"})
        assert response.status_code == 401


def test_rules_post_with_header_token_succeeds(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BENJAMIN_TEST_MODE", "1")
    monkeypatch.setenv("BENJAMIN_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("BENJAMIN_AUTH_MODE", "token")
    monkeypatch.setenv("BENJAMIN_AUTH_TOKEN", "secret-token")
    _reset_deps()

    payload = {
        "name": "api rule",
        "trigger": {"type": "schedule", "every_minutes": 5},
        "condition": {"contains": "heartbeat"},
        "actions": [{"type": "notify", "title": "Rule", "body_template": "Matched {{count}}"}],
    }

    with TestClient(app) as client:
        response = client.post("/rules", json=payload, headers={"X-BENJAMIN-TOKEN": "secret-token"})
        assert response.status_code == 200


def test_login_flow_sets_cookie_and_allows_ui(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BENJAMIN_TEST_MODE", "1")
    monkeypatch.setenv("BENJAMIN_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("BENJAMIN_AUTH_MODE", "token")
    monkeypatch.setenv("BENJAMIN_AUTH_TOKEN", "secret-token")
    _reset_deps()

    with TestClient(app) as client:
        login = client.post("/ui/login", data={"token": "secret-token"}, follow_redirects=False)
        assert login.status_code == 303
        assert login.headers["location"] == "/ui/chat"
        assert "benjamin_token=" in login.headers.get("set-cookie", "")

        ui_chat = client.get("/ui/chat")
        assert ui_chat.status_code == 200


def test_healthz_always_unauthenticated(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BENJAMIN_TEST_MODE", "1")
    monkeypatch.setenv("BENJAMIN_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("BENJAMIN_AUTH_MODE", "token")
    monkeypatch.delenv("BENJAMIN_AUTH_TOKEN", raising=False)
    _reset_deps()

    with TestClient(app) as client:
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json() == {"ok": True}
