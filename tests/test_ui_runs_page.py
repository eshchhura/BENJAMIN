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


def test_ui_runs_page_lists_chat_runs(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BENJAMIN_TEST_MODE", "1")
    monkeypatch.setenv("BENJAMIN_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("BENJAMIN_AUTH_MODE", "off")
    _reset_deps()

    with TestClient(app) as client:
        client.post("/chat/", json={"message": "show runs"})
        response = client.get("/ui/runs")
        assert response.status_code == 200
        body = response.text
        assert "Recent Chats" in body
        assert "Recent Rule Runs" in body
        assert "show runs" in body
