from pathlib import Path

from benjamin.core.approvals.service import ApprovalService
from benjamin.core.approvals.store import ApprovalStore
from benjamin.core.memory.manager import MemoryManager
from benjamin.core.notifications.notifier import NotificationRouter
from benjamin.core.rules.engine import RuleEngine
from benjamin.core.rules.schemas import Rule, RuleActionNotify, RuleActionProposeStep, RuleCondition, RuleTrigger
from benjamin.core.skills.registry import SkillRegistry


class FakeEmailConnector:
    def search_messages(self, query: str, max_results: int) -> list[dict]:
        del query, max_results
        return [{"subject": "Quarterly report", "snippet": "Action required"}]


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


def test_rule_engine_notify_and_propose_step(tmp_path) -> None:
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
        email_connector=FakeEmailConnector(),
    )

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
