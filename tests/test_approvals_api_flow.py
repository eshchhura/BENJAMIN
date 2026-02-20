import json
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from apps.api import deps
from apps.api.main import app


def _reset_deps() -> None:
    deps.get_memory_manager.cache_clear()
    deps.get_scheduler_service.cache_clear()
    deps.get_orchestrator.cache_clear()
    deps.get_approval_store.cache_clear()
    deps.get_approval_service.cache_clear()


def _create_pending_approval(client: TestClient, message: str) -> str:
    response = client.post("/chat/", json={"message": message})
    assert response.status_code == 200
    list_response = client.get("/approvals")
    assert list_response.status_code == 200
    approvals = list_response.json()["approvals"]
    assert approvals
    return approvals[0]["id"]


def test_approvals_api_approve_and_reject_flow(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BENJAMIN_TEST_MODE", "1")
    monkeypatch.setenv("BENJAMIN_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("BENJAMIN_APPROVALS_AUTOCLEAN", "on")
    _reset_deps()

    run_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    payload = json.dumps({"message": "Take medicine", "run_at_iso": run_at})

    with TestClient(app) as client:
        approval_id = _create_pending_approval(client, f"reminders.create {payload}")

        approve_response = client.post(f"/approvals/{approval_id}/approve", json={"approver_note": "ok"})
        assert approve_response.status_code == 200
        approved = approve_response.json()
        assert approved["status"] == "approved"
        assert approved["result"]["ok"] is True

        list_after_approve = client.get("/approvals").json()["approvals"]
        assert all(item["id"] != approval_id for item in list_after_approve)

        episodic = client.get("/memory/episodic", params={"limit": 20}).json()["items"]
        assert any(item["kind"] == "approval" and item["meta"].get("approval_id") == approval_id for item in episodic)

        reject_id = _create_pending_approval(client, f"reminders.create {payload}")
        reject_response = client.post(f"/approvals/{reject_id}/reject", json={"reason": "not now"})
        assert reject_response.status_code == 200
        rejected = reject_response.json()
        assert rejected["status"] == "rejected"

        episodic_after_reject = client.get("/memory/episodic", params={"limit": 20}).json()["items"]
        assert any(
            item["kind"] == "approval"
            and item["meta"].get("approval_id") == reject_id
            and item["meta"].get("reason") == "not now"
            for item in episodic_after_reject
        )
