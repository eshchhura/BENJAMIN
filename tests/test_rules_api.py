from fastapi.testclient import TestClient

from benjamin.apps.api import deps
from benjamin.apps.api.main import app


def test_rules_create_and_list(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BENJAMIN_TEST_MODE", "1")
    monkeypatch.setenv("BENJAMIN_STATE_DIR", str(tmp_path))
    deps.get_memory_manager.cache_clear()
    deps.get_scheduler_service.cache_clear()
    deps.get_orchestrator.cache_clear()
    deps.get_approval_store.cache_clear()
    deps.get_approval_service.cache_clear()
    deps.get_calendar_connector.cache_clear()
    deps.get_email_connector.cache_clear()
    deps.get_notification_router.cache_clear()

    payload = {
        "name": "api rule",
        "trigger": {"type": "schedule", "every_minutes": 5},
        "condition": {"contains": "heartbeat"},
        "actions": [{"type": "notify", "title": "Rule", "body_template": "Matched {{count}}"}],
        "cooldown_minutes": 5,
        "max_actions_per_run": 2,
    }

    with TestClient(app) as client:
        created = client.post("/rules", json=payload)
        assert created.status_code == 200
        listed = client.get("/rules")
        assert listed.status_code == 200
        names = [item["name"] for item in listed.json()]
        assert "api rule" in names
        created_payload = created.json()
        assert created_payload["cooldown_minutes"] == 5
        assert created_payload["max_actions_per_run"] == 2
