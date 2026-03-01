from __future__ import annotations

import logging
from pathlib import Path
from uuid import uuid4

from benjamin.core.approvals.service import ApprovalService
from benjamin.core.approvals.store import ApprovalStore
from benjamin.core.integrations.base import CalendarConnector, EmailConnector
from benjamin.core.ledger.keys import job_run_key
from benjamin.core.ledger.ledger import ExecutionLedger
from benjamin.core.logging.context import log_context
from benjamin.core.memory.manager import MemoryManager
from benjamin.core.notifications.notifier import NotificationRouter, build_notification_router
from benjamin.core.orchestration.orchestrator import Orchestrator

from .engine import RuleEngine
from .schemas import RuleRunResult
from .store import RuleStore


logger = logging.getLogger("benjamin.rules.evaluator")


def run_rules_evaluation(
    state_dir: str,
    job_id: str | None = None,
    scheduled_run_iso: str | None = None,
    router: NotificationRouter | None = None,
    calendar_connector: CalendarConnector | None = None,
    email_connector: EmailConnector | None = None,
) -> list[RuleRunResult]:
    memory_manager = MemoryManager(state_dir=Path(state_dir))
    ledger = ExecutionLedger(memory_manager.state_dir)
    run_correlation_id = str(uuid4())
    effective_job_id = job_id or "rules-evaluator"
    job_key: str | None = None
    with log_context(correlation_id=run_correlation_id, job_id=effective_job_id):
        logger.info("rules_evaluation_started")
        if job_id is not None:
            job_key = job_run_key(job_id=effective_job_id, scheduled_run_iso=scheduled_run_iso)
            started = ledger.try_start(
                job_key,
                kind="job_run",
                correlation_id=run_correlation_id,
                meta={"job_id": effective_job_id, "scheduled_run_iso": scheduled_run_iso},
            )
            if not started:
                memory_manager.episodic.append(
                    kind="rule",
                    summary="Skipped duplicate rules evaluator run",
                    meta={"correlation_id": run_correlation_id, "job_id": effective_job_id, "skipped_idempotent": True},
                )
                logger.info("job_completed", extra={"extra_fields": {"skipped_idempotent": True}})
                return []

        orchestrator = Orchestrator(
            memory_manager=memory_manager,
            calendar_connector=calendar_connector,
            email_connector=email_connector,
        )
        approval_service = ApprovalService(store=ApprovalStore(memory_manager.state_dir), memory_manager=memory_manager, ledger=ledger)
        rule_store = RuleStore(memory_manager.state_dir)
        rule_engine = RuleEngine(
            memory_manager=memory_manager,
            approval_service=approval_service,
            registry=orchestrator.registry,
            notifier=router or build_notification_router(),
            email_connector=email_connector,
            calendar_connector=calendar_connector,
            ledger=ledger,
        )

        results: list[RuleRunResult] = []
        try:
            for rule in rule_store.list_all():
                if not rule.enabled:
                    continue
                result = rule_engine.evaluate_rule(rule, ctx={"correlation_id": run_correlation_id})
                rule_store.upsert(rule)
                results.append(result)
            if job_key is not None:
                ledger.mark(job_key, "succeeded", meta_update={"rule_count": len(results)})
            logger.info("rules_evaluation_completed", extra={"extra_fields": {"rule_count": len(results)}})
            return results
        except Exception as exc:
            if job_key is not None:
                ledger.mark(job_key, "failed", meta_update={"error": str(exc)})
            logger.exception("rules_evaluation_completed")
            raise
