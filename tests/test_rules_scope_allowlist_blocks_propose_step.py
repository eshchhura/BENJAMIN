from pathlib import Path

from benjamin.core.approvals.service import ApprovalService
from benjamin.core.approvals.store import ApprovalStore
from benjamin.core.memory.manager import MemoryManager
from benjamin.core.notifications.notifier import NotificationRouter
from benjamin.core.rules.engine import RuleEngine
from benjamin.core.rules.schemas import Rule, RuleActionProposeStep, RuleCondition, RuleTrigger
from benjamin.core.skills.registry import SkillRegistry


class EmailStub:
    def search_messages(self, query: str, max_results: int) -> list[dict]:
        return [
            {
                "id": "m1",
                "thread_id": "t1",
                "date_iso": "2026-01-01T10:00:00+00:00",
                "subject": "planning",
                "snippet": "calendar planning",
            }
        ]


class NoopNotifier:
    def send(self, title: str, body: str, meta: dict | None = None) -> None:
        del title, body, meta


class CalendarWriteSkill:
    name = "calendar.create_event"
    side_effect = "write"

    def run(self, query: str):
        del query


def test_rules_scope_allowlist_blocks_propose_step(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BENJAMIN_RULES_ALLOWED_SCOPES", "reminders.write")
    monkeypatch.setenv("BENJAMIN_SCOPES_ENABLED", "calendar.write")

    memory = MemoryManager(state_dir=Path(tmp_path))
    approvals = ApprovalService(store=ApprovalStore(state_dir=memory.state_dir), memory_manager=memory)
    registry = SkillRegistry()
    registry.register(CalendarWriteSkill())
    engine = RuleEngine(
        memory_manager=memory,
        approval_service=approvals,
        registry=registry,
        notifier=NotificationRouter(channels=[NoopNotifier()]),
        email_connector=EmailStub(),
    )

    rule = Rule(
        name="calendar proposal blocked",
        trigger=RuleTrigger(type="gmail", query="planning", max_results=1),
        condition=RuleCondition(contains="planning"),
        actions=[
            RuleActionProposeStep(
                type="propose_step",
                skill_name="calendar.create_event",
                args={"title": "Planning"},
                rationale="Need approval",
            )
        ],
    )

    result = engine.evaluate_rule(rule)

    assert result.ok is True
    assert "rules_scope_blocked" in result.notes
    assert approvals.store.list_all(status="pending") == []
