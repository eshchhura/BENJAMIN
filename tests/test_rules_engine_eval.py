from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from benjamin.apps.api import deps
from benjamin.apps.api.main import app
from benjamin.core.approvals.service import ApprovalService
from benjamin.core.approvals.store import ApprovalStore
from benjamin.core.memory.manager import MemoryManager
from benjamin.core.notifications.notifier import NotificationRouter
from benjamin.core.rules.engine import RuleEngine
from benjamin.core.rules.schemas import Rule, RuleActionNotify, RuleActionProposeStep, RuleCondition, RuleTrigger
from benjamin.core.skills.registry import SkillRegistry


class FakeEmailConnector:
    def __init__(self, messages: list[dict] | None = None) -> None:
        self.messages = messages or [{"subject": "Quarterly report", "snippet": "Action required", "id": "1"}]

    def search_messages(self, query: str, max_results: int) -> list[dict]:
        del query
        return self.messages[:max_results]


class RecordingNotifier:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def send(self, title: str, body: str, meta: dict | None = None) -> None:
        self.calls.append({"title": title, "body": body, "meta": meta or {}})


class DummyWriteSkill:
    name = "dummy.write"
    side_effect = "write"

    def run(self, query: str):  # pragma: no cover
        del query
        return None


def _engine(tmp_path, email_connector=None):
    memory = MemoryManager(state_dir=Path(tmp_path))
    approval_service = ApprovalService(store=ApprovalStore(state_dir=memory.state_dir), memory_manager=memory)
    notifier = RecordingNotifier()
    registry = SkillRegistry()
    registry.register(DummyWriteSkill())
    engine = RuleEngine(
        memory_manager=memory,
        approval_service=approval_service,
        registry=registry,
        notifier=NotificationRouter(channels=[notifier]),
        email_connector=email_connector or FakeEmailConnector(),
    )
    return engine, notifier, approval_service


def test_rule_engine_notify_and_propose_step(tmp_path) -> None:
    engine, notifier, approval_service = _engine(tmp_path)

    notify_rule = Rule(
        name="notify rule",
        trigger=RuleTrigger(type="gmail", query="report", max_results=5),
        condition=RuleCondition(contains="report"),
        actions=[RuleActionNotify(type="notify", title="Inbox", body_template="Count={{count}} top={{top1}}")],
    )
    notify_result = engine.evaluate_rule(notify_rule)
    assert notify_result.ok is True
    assert notify_result.matched is True
    assert notifier.calls

    approval_rule = Rule(
        name="approval rule",
        trigger=RuleTrigger(type="gmail", query="report", max_results=5),
        condition=RuleCondition(contains="report"),
        actions=[
            RuleActionProposeStep(
                type="propose_step",
                skill_name="dummy.write",
                args={"value": "123"},
                rationale="Need user confirmation",
            )
        ],
    )
    approval_result = engine.evaluate_rule(approval_rule)
    assert approval_result.ok is True
    approvals = approval_service.store.list_all(status="pending")
    assert len(approvals) == 1
    assert approvals[0].step.skill_name == "dummy.write"


def test_rules_dedupe_since_cursor_gmail(tmp_path) -> None:
    messages = [
        {"id": "m1", "thread_id": "t1", "date_iso": "2026-01-01T10:00:00+00:00", "subject": "Report", "snippet": "alpha"},
        {"id": "m2", "thread_id": "t2", "date_iso": "2026-01-01T10:05:00+00:00", "subject": "Report", "snippet": "beta"},
        {"id": "m3", "thread_id": "t3", "date_iso": "2026-01-01T10:10:00+00:00", "subject": "Report", "snippet": "gamma"},
    ]
    engine, notifier, _ = _engine(tmp_path, email_connector=FakeEmailConnector(messages))
    rule = Rule(
        name="gmail dedupe",
        trigger=RuleTrigger(type="gmail", query="report", max_results=5),
        condition=RuleCondition(contains="report"),
        actions=[RuleActionNotify(type="notify", title="Inbox", body_template="Count={{count}}")],
    )

    first = engine.evaluate_rule(rule)
    second = engine.evaluate_rule(rule)

    assert first.matched is True
    assert first.match_count == 3
    assert second.matched is False
    assert second.match_count == 0
    assert len(notifier.calls) == 1
    assert set(rule.state.seen_ids) == {"t1", "t2", "t3"}
    assert rule.state.last_cursor_iso == "2026-01-01T10:10:00+00:00"


def test_rules_cooldown_blocks_repeat(tmp_path) -> None:
    engine, notifier, _ = _engine(tmp_path)
    rule = Rule(
        name="cooldown",
        trigger=RuleTrigger(type="gmail", query="report", max_results=5),
        condition=RuleCondition(contains="report"),
        actions=[RuleActionNotify(type="notify", title="Inbox", body_template="Count={{count}}")],
        cooldown_minutes=60,
    )

    first = engine.evaluate_rule(rule)
    second = engine.evaluate_rule(rule)

    assert first.matched is True
    assert second.matched is False
    assert "cooldown_active" in second.notes
    assert len(notifier.calls) == 1
    assert rule.state.cooldown_until_iso is not None
    assert rule.state.last_run_iso is not None


def test_action_cap(tmp_path) -> None:
    engine, notifier, approval_service = _engine(tmp_path)
    rule = Rule(
        name="cap",
        trigger=RuleTrigger(type="gmail", query="report", max_results=5),
        condition=RuleCondition(contains="report"),
        max_actions_per_run=1,
        actions=[
            RuleActionNotify(type="notify", title="Inbox", body_template="Count={{count}}"),
            RuleActionProposeStep(
                type="propose_step",
                skill_name="dummy.write",
                args={"value": "123"},
                rationale="Need user confirmation",
            ),
        ],
    )

    result = engine.evaluate_rule(rule)
    assert result.matched is True
    assert "action_cap_reached" in result.notes
    assert len(notifier.calls) == 1
    assert approval_service.store.list_all(status="pending") == []


def test_rules_reset_state(tmp_path, monkeypatch) -> None:
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
        "name": "api reset",
        "trigger": {"type": "schedule", "every_minutes": 5},
        "actions": [{"type": "notify", "title": "Rule", "body_template": "Matched {{count}}"}],
    }

    with TestClient(app) as client:
        created = client.post("/rules", json=payload)
        rule_id = created.json()["id"]

        eval_one = client.post("/rules/evaluate-now")
        assert eval_one.status_code == 200

        fetched = client.get("/rules").json()[0]
        assert fetched["state"]["last_run_iso"] is not None

        reset = client.post(f"/rules/{rule_id}/reset-state")
        assert reset.status_code == 200
        assert reset.json()["state"]["last_run_iso"] is None
        assert reset.json()["state"]["seen_ids"] == []

        eval_two = client.post("/rules/evaluate-now")
        assert eval_two.status_code == 200
        assert eval_two.json()["results"][0]["matched"] is True
