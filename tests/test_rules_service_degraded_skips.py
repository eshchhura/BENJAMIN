from benjamin.core.infra.breaker_manager import BreakerManager
from benjamin.core.approvals.store import ApprovalStore
from benjamin.core.rules.evaluator import run_rules_evaluation
from benjamin.core.rules.schemas import Rule, RuleActionProposeStep, RuleCondition, RuleTrigger
from benjamin.core.rules.store import RuleStore


class BrokenEmailConnector:
    def _raise(self):
        raise RuntimeError("gmail_down")

    def search_messages(self, query: str, max_results: int):
        return self._raise()


def test_rules_skip_when_gmail_degraded(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("BENJAMIN_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("BENJAMIN_BREAKER_FAILURE_THRESHOLD", "1")

    rule_store = RuleStore(tmp_path)
    rule_store.upsert(
        Rule(
            name="gmail rule",
            trigger=RuleTrigger(type="gmail", query="from:foo", max_results=5),
            condition=RuleCondition(contains="foo"),
            actions=[
                RuleActionProposeStep(
                    type="propose_step",
                    skill_name="gmail.draft_email",
                    args={"to": ["a@b.com"], "subject": "x", "body": "y"},
                    rationale="respond",
                )
            ],
        )
    )

    manager = BreakerManager(state_dir=tmp_path)

    class GuardedBrokenEmailConnector(BrokenEmailConnector):
        def search_messages(self, query: str, max_results: int):
            return manager.wrap("gmail", lambda: BrokenEmailConnector.search_messages(self, query, max_results))

    connector = GuardedBrokenEmailConnector()
    first = run_rules_evaluation(
        state_dir=str(tmp_path),
        email_connector=connector,
        calendar_connector=None,
    )
    second = run_rules_evaluation(
        state_dir=str(tmp_path),
        email_connector=connector,
        calendar_connector=None,
    )

    assert first
    assert second
    assert any("service_degraded:gmail" in note for note in second[0].notes)
    assert ApprovalStore(tmp_path).list_all() == []
