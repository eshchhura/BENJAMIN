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


def test_safe_mode_prevents_write_approval_creation_in_chat(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BENJAMIN_TEST_MODE", "1")
    monkeypatch.setenv("BENJAMIN_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("BENJAMIN_SAFE_MODE", "on")
    _reset_deps()

    run_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    payload = json.dumps({"message": "Take medicine", "run_at_iso": run_at})

    with TestClient(app) as client:
        response = client.post("/chat/", json={"message": f"reminders.create {payload}"})
        assert response.status_code == 200
        assert "Safe mode enabled" in response.json()["response"]

        approvals = client.get("/approvals").json()["approvals"]
        assert approvals == []
