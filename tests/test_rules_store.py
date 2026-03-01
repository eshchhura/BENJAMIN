from benjamin.core.rules.schemas import Rule, RuleActionNotify, RuleTrigger
from benjamin.core.rules.store import RuleStore


def test_rules_store_crud_and_enable(tmp_path) -> None:
    store = RuleStore(state_dir=tmp_path)
    rule = Rule(
        name="Inbox monitor",
        trigger=RuleTrigger(type="schedule"),
        actions=[RuleActionNotify(type="notify", title="t", body_template="b")],
    )

    created = store.upsert(rule)
    assert store.get(created.id) is not None
    assert len(store.list_all()) == 1

    disabled = store.set_enabled(created.id, False)
    assert disabled is not None
    assert disabled.enabled is False

    enabled = store.set_enabled(created.id, True)
    assert enabled is not None
    assert enabled.enabled is True

    assert store.delete(created.id) is True
    assert store.get(created.id) is None
