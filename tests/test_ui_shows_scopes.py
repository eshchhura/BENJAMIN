import json
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from benjamin.apps.api import deps
from benjamin.apps.api.main import app


def _reset_deps() -> None:
    deps.get_memory_manager.cache_clear()
    deps.get_scheduler_service.cache_clear()
    deps.get_orchestrator.cache_clear()
    deps.get_approval_store.cache_clear()
    deps.get_approval_service.cache_clear()


def test_ui_approvals_contains_scope_status_text(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BENJAMIN_TEST_MODE", "1")
    monkeypatch.setenv("BENJAMIN_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("BENJAMIN_APPROVALS_AUTOCLEAN", "off")
    monkeypatch.setenv("BENJAMIN_SCOPES_ENABLED", "calendar.write")
    _reset_deps()

    payload = json.dumps(
        {
            "title": "1:1",
            "start_iso": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            "end_iso": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
        }
    )
    with TestClient(app) as client:
        client.post("/chat/", json={"message": f"calendar.create_event {payload}"})
        response = client.get("/ui/approvals")
        assert response.status_code == 200
        assert "calendar.write" in response.text
        assert "enabled" in response.text
