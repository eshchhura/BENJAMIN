from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import HTTPException

from benjamin.core.ledger.keys import approval_execution_key
from benjamin.core.ledger.ledger import ExecutionLedger
from benjamin.core.approvals.schemas import PendingApproval
from benjamin.core.approvals.store import ApprovalStore, now_iso
from benjamin.core.logging.context import correlation_id_var, log_context
from benjamin.core.memory.manager import MemoryManager
from benjamin.core.orchestration.planner import Plan
from benjamin.core.orchestration.schemas import ContextPack, PlanStep, StepResult
from benjamin.core.security.policy import PermissionsPolicy
from benjamin.core.security.scopes import default_scopes_for_skill
from benjamin.core.skills.registry import SkillRegistry


class ApprovalService:
    def __init__(
        self,
        store: ApprovalStore,
        memory_manager: MemoryManager,
        ledger: ExecutionLedger | None = None,
        permissions_policy: PermissionsPolicy | None = None,
    ) -> None:
        self.store = store
        self.memory_manager = memory_manager
        self.ledger = ledger or ExecutionLedger(memory_manager.state_dir)
        self.logger = logging.getLogger("benjamin.approvals")
        self.permissions_policy = permissions_policy or PermissionsPolicy()

    def create_pending(
        self,
        step: PlanStep,
        ctx: ContextPack,
        requester: dict,
        rationale: str,
        registry: SkillRegistry,
        required_scopes: list[str] | None = None,
    ) -> PendingApproval:
        if not step.skill_name:
            raise ValueError("approval requires a skill step")
        skill = registry.get(step.skill_name)
        if getattr(skill, "side_effect", "read") != "write":
            raise ValueError("approval can only be created for write skills")

        scopes = list(required_scopes or getattr(skill, "required_scopes", []) or [])
        if not scopes:
            scopes = default_scopes_for_skill(skill.name, getattr(skill, "side_effect", "read"))
        scopes_ok, disabled_scopes = self.permissions_policy.check_scopes(scopes)
        if not scopes_ok:
            raise ValueError(f"policy_denied:{','.join(disabled_scopes)}")

        created_at = datetime.now(timezone.utc)
        ttl_hours = int(os.getenv("BENJAMIN_APPROVALS_TTL_HOURS", "72"))
        correlation_id = str(requester.get("correlation_id") or correlation_id_var.get() or uuid4())
        enriched_requester = dict(requester)
        enriched_requester.setdefault("correlation_id", correlation_id)
        record = PendingApproval(
            id=str(uuid4()),
            created_at_iso=created_at.isoformat(),
            expires_at_iso=(created_at + timedelta(hours=ttl_hours)).isoformat(),
            status="pending",
            requester=enriched_requester,
            step=step,
            context={"cwd": ctx.cwd, "goal": ctx.goal},
            rationale=rationale,
            required_scopes=scopes,
            policy_snapshot={"enabled": scopes_ok, "disabled_scopes": disabled_scopes},
        )
        self.store.upsert(record)
        return record

    def is_expired(self, record: PendingApproval, now: datetime) -> bool:
        return datetime.fromisoformat(record.expires_at_iso) <= now

    def approve(self, id: str, approver_note: str | None, executor, registry: SkillRegistry) -> PendingApproval:
        record = self.store.get(id)
        if record is None:
            raise HTTPException(status_code=404, detail="approval not found")

        if record.status == "approved":
            response_record = record.model_copy(deep=True)
            response_record.result = StepResult(
                step_id=record.step.id,
                ok=True,
                output='{"skipped":true,"reason":"idempotent_duplicate"}',
            )
            return response_record

        if record.status != "pending":
            raise HTTPException(status_code=400, detail=f"approval is {record.status}")

        now = datetime.now(timezone.utc)
        if self.is_expired(record, now):
            record.status = "expired"
            record.error = "approval expired"
            self._persist_or_clean(record)
            raise HTTPException(status_code=400, detail="approval expired")

        active_policy = PermissionsPolicy()
        scopes_ok, disabled_scopes = active_policy.check_scopes(record.required_scopes)
        if not scopes_ok:
            record.status = "rejected"
            record.error = f"policy_denied:{','.join(disabled_scopes)}"
            self.memory_manager.episodic.append(
                kind="approval",
                summary=f"Rejected {record.step.skill_name} due to policy",
                meta={"approval_id": record.id, "step_id": record.step.id, "disabled_scopes": disabled_scopes},
            )
            self._persist_or_clean(record)
            raise HTTPException(status_code=400, detail="policy_denied")

        correlation_id = str(record.requester.get("correlation_id") or correlation_id_var.get() or uuid4())
        started_at = time.perf_counter()
        with log_context(correlation_id=correlation_id, approval_id=record.id):
            self.logger.info("approval_exec_started")
            execution_key = approval_execution_key(record.id, record.step)
            started = self.ledger.try_start(
                execution_key,
                kind="approval_exec",
                correlation_id=correlation_id,
                meta={"approval_id": record.id, "skill_name": record.step.skill_name},
            )
            if not started:
                record.status = "approved"
                record.result = StepResult(
                    step_id=record.step.id,
                    ok=True,
                    output='{"skipped":true,"reason":"idempotent_duplicate"}',
                )
                record.error = None
                self.memory_manager.episodic.append(
                    kind="approval",
                    summary=f"Skipped duplicate approval for {record.step.skill_name}",
                    meta={
                        "approval_id": record.id,
                        "step_id": record.step.id,
                        "ok": True,
                        "approver_note": approver_note,
                        "correlation_id": correlation_id,
                        "skipped": True,
                        "reason": "idempotent_duplicate",
                    },
                )
                record.requester = {**record.requester, "correlation_id": correlation_id}
                self._persist_or_clean(record)
                self.logger.info(
                    "approval_exec_completed",
                    extra={"extra_fields": {"status": "skipped", "duration_ms": int((time.perf_counter() - started_at) * 1000)}},
                )
                return record

            context = ContextPack(goal=record.context.get("goal", "approved execution"), cwd=record.context.get("cwd"))
            try:
                result = executor.execute_plan(
                    Plan(goal=context.goal, steps=[record.step]),
                    context=context,
                    registry=registry,
                    trace=None,
                    approval_service=self,
                    requester={"source": "approval", "approval_id": record.id, "approver_note": approver_note, "correlation_id": correlation_id},
                    force_execute_writes=True,
                )[0]
            except Exception as exc:
                self.ledger.mark(execution_key, "failed", meta_update={"error": str(exc)})
                self.logger.exception("approval_exec_completed", extra={"extra_fields": {"status": "failed"}})
                raise

            if result.ok:
                self.ledger.mark(execution_key, "succeeded")
            else:
                self.ledger.mark(execution_key, "failed", meta_update={"error": result.error or "execution_failed"})
            record.status = "approved"
            record.result = result
            record.error = result.error
            self.memory_manager.episodic.append(
                kind="approval",
                summary=f"Approved and executed {record.step.skill_name}",
                meta={"approval_id": record.id, "step_id": record.step.id, "ok": result.ok, "approver_note": approver_note, "correlation_id": correlation_id},
            )
            record.requester = {**record.requester, "correlation_id": correlation_id}
            self._persist_or_clean(record)
            self.logger.info(
                "approval_exec_completed",
                extra={
                    "extra_fields": {
                        "status": "ok" if result.ok else "failed",
                        "duration_ms": int((time.perf_counter() - started_at) * 1000),
                    }
                },
            )
            return record

    def reject(self, id: str, reason: str | None) -> PendingApproval:
        record = self.store.get(id)
        if record is None:
            raise HTTPException(status_code=404, detail="approval not found")
        if record.status != "pending":
            raise HTTPException(status_code=400, detail=f"approval is {record.status}")

        now = datetime.now(timezone.utc)
        if self.is_expired(record, now):
            record.status = "expired"
            record.error = "approval expired"
            self._persist_or_clean(record)
            raise HTTPException(status_code=400, detail="approval expired")

        correlation_id = str(record.requester.get("correlation_id") or correlation_id_var.get() or uuid4())
        with log_context(correlation_id=correlation_id, approval_id=record.id):
            self.logger.info("approval_exec_started", extra={"extra_fields": {"action": "reject"}})
            record.status = "rejected"
            record.error = reason
            self.memory_manager.episodic.append(
                kind="approval",
                summary=f"Rejected {record.step.skill_name}",
                meta={"approval_id": record.id, "reason": reason, "correlation_id": correlation_id},
            )
            record.requester = {**record.requester, "correlation_id": correlation_id}
            self._persist_or_clean(record)
            self.logger.info("approval_exec_completed", extra={"extra_fields": {"status": "rejected"}})
            return record

    def cleanup_expired(self) -> int:
        return self.store.cleanup_expired(now_iso())

    def _persist_or_clean(self, record: PendingApproval) -> None:
        autoclean = os.getenv("BENJAMIN_APPROVALS_AUTOCLEAN", "on").casefold() != "off"
        if autoclean and record.status in {"approved", "rejected", "expired"}:
            self.store.delete(record.id)
        else:
            self.store.upsert(record)
