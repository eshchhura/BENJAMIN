from datetime import datetime, timedelta, timezone

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


def test_rule_test_mode_does_not_mutate_state_or_execute_side_effects(tmp_path, monkeypatch) -> None:
    _reset_deps(tmp_path, monkeypatch)

    now = datetime.now(timezone.utc)
    cooldown_until = (now + timedelta(minutes=15)).isoformat()

    payload = {
        "name": "dry-run side-effects",
        "trigger": {"type": "gmail", "query": "report", "max_results": 5},
        "condition": {"contains": "report"},
        "actions": [
            {
                "type": "notify",
                "title": "Inbox digest",
                "body_template": "Matched {{count}}",
            },
            {
                "type": "propose_step",
                "skill_name": "gmail.send_email",
                "args": {"to": "dev@example.com", "subject": "Review"},
                "rationale": "Needs confirmation",
            },
        ],
        "cooldown_minutes": 30,
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
        rule_id = created.json()["id"]

        stored_rule = client.app.state.rule_store.get(rule_id)
        assert stored_rule is not None
        seeded_state = stored_rule.state.model_copy(
            update={
                "last_run_iso": "2026-01-01T09:00:00+00:00",
                "last_match_iso": "2026-01-01T09:00:00+00:00",
                "cooldown_until_iso": cooldown_until,
                "seen_ids": ["thread-older"],
                "last_cursor_iso": "2026-01-01T09:00:00+00:00",
            }
        )
        client.app.state.rule_store.upsert(
            stored_rule.model_copy(
                update={
                    "state": seeded_state,
                    "last_run_iso": "2026-01-01T09:00:00+00:00",
                    "last_match_iso": "2026-01-01T09:00:00+00:00",
                }
            )
        )

        approval_calls = 0
        notify_calls = 0

        def _count_approval(*args, **kwargs):
            nonlocal approval_calls
            approval_calls += 1
            raise AssertionError("create_pending should not be called in dry-run")

        def _count_notify(*args, **kwargs):
            nonlocal notify_calls
            notify_calls += 1
            raise AssertionError("send should not be called in dry-run")

        monkeypatch.setattr(client.app.state.approval_service, "create_pending", _count_approval)
        monkeypatch.setattr(client.app.state.notification_router, "send", _count_notify)

        tested = client.post(f"/rules/{rule_id}/test")
        assert tested.status_code == 200
        tested_payload = tested.json()
        assert "blocked_by_cooldown" in tested_payload["notes"]
        assert tested_payload["planned_actions"] == []

        fetched = client.get("/rules")
        stored = next(item for item in fetched.json() if item["id"] == rule_id)

    assert stored["state"]["last_run_iso"] == "2026-01-01T09:00:00+00:00"
    assert stored["state"]["last_match_iso"] == "2026-01-01T09:00:00+00:00"
    assert stored["state"]["cooldown_until_iso"] == cooldown_until
    assert stored["state"]["seen_ids"] == ["thread-older"]
    assert stored["state"]["last_cursor_iso"] == "2026-01-01T09:00:00+00:00"
    assert stored["last_run_iso"] == "2026-01-01T09:00:00+00:00"
    assert stored["last_match_iso"] == "2026-01-01T09:00:00+00:00"
    assert approval_calls == 0
    assert notify_calls == 0
