from __future__ import annotations

from pathlib import Path

from benjamin.core.approvals.service import ApprovalService
from benjamin.core.approvals.store import ApprovalStore
from benjamin.core.integrations.base import CalendarConnector, EmailConnector
from benjamin.core.memory.manager import MemoryManager
from benjamin.core.notifications.notifier import NotificationRouter, build_notification_router
from benjamin.core.orchestration.orchestrator import Orchestrator

from .engine import RuleEngine
from .schemas import RuleRunResult, now_iso
from .store import RuleStore


def run_rules_evaluation(
    state_dir: str,
    router: NotificationRouter | None = None,
    calendar_connector: CalendarConnector | None = None,
    email_connector: EmailConnector | None = None,
) -> list[RuleRunResult]:
    memory_manager = MemoryManager(state_dir=Path(state_dir))
    orchestrator = Orchestrator(
        memory_manager=memory_manager,
        calendar_connector=calendar_connector,
        email_connector=email_connector,
    )
    approval_service = ApprovalService(store=ApprovalStore(memory_manager.state_dir), memory_manager=memory_manager)
    rule_store = RuleStore(memory_manager.state_dir)
    rule_engine = RuleEngine(
        memory_manager=memory_manager,
        approval_service=approval_service,
        registry=orchestrator.registry,
        notifier=router or build_notification_router(),
        email_connector=email_connector,
        calendar_connector=calendar_connector,
    )

    results: list[RuleRunResult] = []
    for rule in rule_store.list_all():
        if not rule.enabled:
            continue
        result = rule_engine.evaluate_rule(rule)
        updates = {"last_run_iso": now_iso()}
        if result.matched:
            updates["last_match_iso"] = now_iso()
        rule_store.upsert(rule.model_copy(update=updates))
        results.append(result)
    return results
