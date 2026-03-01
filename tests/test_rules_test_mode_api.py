from fastapi.testclient import TestClient

from benjamin.apps.api import deps
from benjamin.apps.api.main import app


def _reset_deps(tmp_path, monkeypatch) -> None:
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


def test_rule_test_endpoint_returns_preview_with_rendered_notify(tmp_path, monkeypatch) -> None:
    _reset_deps(tmp_path, monkeypatch)

    payload = {
        "name": "dry-run notify",
        "trigger": {"type": "gmail", "query": "report", "max_results": 5},
        "condition": {"contains": "report"},
        "actions": [
            {
                "type": "notify",
                "title": "Inbox digest",
                "body_template": "Matched {{count}} top={{top1}} at {{now_iso}}",
            }
        ],
    }

    with TestClient(app) as client:
        class _EmailStub:
            def search_messages(self, query: str, max_results: int):
                del query
                return [
                    {
                        "id": "msg-1",
                        "thread_id": "thread-123",
                        "subject": "Quarterly report",
                        "snippet": "Report is ready",
                        "from": "ceo@example.com",
                        "date_iso": "2026-01-01T10:00:00+00:00",
                    }
                ][:max_results]

        client.app.state.email_connector = _EmailStub()

        created = client.post("/rules", json=payload)
        assert created.status_code == 200
        rule_id = created.json()["id"]

        tested = client.post(f"/rules/{rule_id}/test")
        assert tested.status_code == 200
        body = tested.json()

    assert body["matched"] is True
    assert body["match_count"] == 1
    assert body["matching_items"][0]["item_id"] == "thread-123"
    assert body["planned_actions"][0]["type"] == "notify"
    assert body["planned_actions"][0]["title"] == "Inbox digest"
    assert "Matched 1" in body["planned_actions"][0]["body"]
    assert "Quarterly report" in body["planned_actions"][0]["body"]
