from pathlib import Path

from benjamin.core.approvals.service import ApprovalService
from benjamin.core.approvals.store import ApprovalStore
from benjamin.core.ledger.keys import rule_action_key
from benjamin.core.ledger.ledger import ExecutionLedger
from benjamin.core.memory.manager import MemoryManager
from benjamin.core.notifications.notifier import NotificationRouter
from benjamin.core.rules.engine import RuleEngine
from benjamin.core.rules.schemas import Rule, RuleActionProposeStep, RuleCondition, RuleTrigger
from benjamin.core.skills.registry import SkillRegistry


class StableEmailConnector:
    def search_messages(self, query: str, max_results: int) -> list[dict]:
        del query
        return [
            {
                "id": "msg_1",
                "thread_id": "thread_1",
                "date_iso": "2026-01-01T10:00:00+00:00",
                "subject": "Need follow-up",
                "snippet": "please respond",
            }
        ][:max_results]


class DummyWriteSkill:
    name = "dummy.write"
    side_effect = "write"

    def run(self, query: str):  # pragma: no cover
        del query
        return None


class NoopNotifier:
    def send(self, title: str, body: str, meta: dict | None = None) -> None:
        del title, body, meta


def test_rule_evaluation_does_not_create_duplicate_proposed_approvals(tmp_path) -> None:
    memory = MemoryManager(state_dir=Path(tmp_path))
    ledger = ExecutionLedger(memory.state_dir)
    approvals = ApprovalService(store=ApprovalStore(state_dir=memory.state_dir), memory_manager=memory, ledger=ledger)

    registry = SkillRegistry()
    registry.register(DummyWriteSkill())

    engine = RuleEngine(
        memory_manager=memory,
        approval_service=approvals,
        registry=registry,
        notifier=NotificationRouter(channels=[NoopNotifier()]),
        email_connector=StableEmailConnector(),
        ledger=ledger,
    )

    rule = Rule(
        name="propose once",
        trigger=RuleTrigger(type="gmail", query="subject:follow-up", max_results=5),
        condition=RuleCondition(contains="follow-up"),
        actions=[
            RuleActionProposeStep(
                type="propose_step",
                skill_name="dummy.write",
                args={"value": "123"},
                rationale="Needs confirmation",
            )
        ],
    )

    first = engine.evaluate_rule(rule)
    # Simulate a restart/race path where item cursors were not persisted yet.
    rule.state.seen_ids = []
    rule.state.last_cursor_iso = None
    second = engine.evaluate_rule(rule)

    pending = approvals.store.list_all(status="pending")
    assert first.ok is True
    assert second.ok is True
    assert len(pending) == 1

    key = rule_action_key(
        rule_id=rule.id,
        action_index=0,
        item_id="thread_1",
        signature={"skill_name": "dummy.write", "args": {"value": "123"}, "rationale": "Needs confirmation"},
    )
    assert ledger.has_succeeded(key) is True
    assert "deduped_by_ledger" in second.notes
