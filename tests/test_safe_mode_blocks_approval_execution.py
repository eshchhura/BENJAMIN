import json
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from benjamin.apps.api import deps
from benjamin.apps.api.main import app
from benjamin.core.ops.safe_mode import set_safe_mode_enabled


def _reset_deps() -> None:
    deps.get_memory_manager.cache_clear()
    deps.get_scheduler_service.cache_clear()
    deps.get_orchestrator.cache_clear()
    deps.get_approval_store.cache_clear()
    deps.get_approval_service.cache_clear()


def test_safe_mode_blocks_approval_execution(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BENJAMIN_TEST_MODE", "1")
    monkeypatch.setenv("BENJAMIN_STATE_DIR", str(tmp_path))
    _reset_deps()

    run_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    payload = json.dumps({"message": "Take medicine", "run_at_iso": run_at})

    with TestClient(app) as client:
        chat = client.post("/chat/", json={"message": f"reminders.create {payload}"})
        assert chat.status_code == 200
        approval_id = client.get("/approvals").json()["approvals"][0]["id"]

        set_safe_mode_enabled(tmp_path, True)
        response = client.post(f"/approvals/{approval_id}/approve", json={"approver_note": "ok"})

        assert response.status_code == 409
        assert "Safe mode enabled" in response.json()["detail"]
        still_pending = client.get("/approvals").json()["approvals"][0]
        assert still_pending["status"] == "pending"
