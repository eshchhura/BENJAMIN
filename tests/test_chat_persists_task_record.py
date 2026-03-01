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


def test_chat_persists_task_record(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BENJAMIN_TEST_MODE", "1")
    monkeypatch.setenv("BENJAMIN_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("BENJAMIN_AUTH_MODE", "off")
    _reset_deps()

    with TestClient(app) as client:
        response = client.post("/chat/", json={"message": "hello"})
        assert response.status_code == 200
        payload = response.json()
        assert payload.get("task_id")

        record = client.app.state.task_store.get(payload["task_id"])
        assert record is not None
        assert record.task_id == payload["task_id"]
        assert record.user_message == "hello"
