from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import HTTPException

from core.approvals.schemas import PendingApproval
from core.approvals.store import ApprovalStore, now_iso
from core.memory.manager import MemoryManager
from core.orchestration.planner import Plan
from core.orchestration.schemas import ContextPack, PlanStep
from core.skills.registry import SkillRegistry


class ApprovalService:
    def __init__(self, store: ApprovalStore, memory_manager: MemoryManager) -> None:
        self.store = store
        self.memory_manager = memory_manager

    def create_pending(self, step: PlanStep, ctx: ContextPack, requester: dict, rationale: str, registry: SkillRegistry) -> PendingApproval:
        if not step.skill_name:
            raise ValueError("approval requires a skill step")
        skill = registry.get(step.skill_name)
        if getattr(skill, "side_effect", "read") != "write":
            raise ValueError("approval can only be created for write skills")

        created_at = datetime.now(timezone.utc)
        ttl_hours = int(os.getenv("BENJAMIN_APPROVALS_TTL_HOURS", "72"))
        record = PendingApproval(
            id=str(uuid4()),
            created_at_iso=created_at.isoformat(),
            expires_at_iso=(created_at + timedelta(hours=ttl_hours)).isoformat(),
            status="pending",
            requester=requester,
            step=step,
            context={"cwd": ctx.cwd, "goal": ctx.goal},
            rationale=rationale,
        )
        self.store.upsert(record)
        return record

    def is_expired(self, record: PendingApproval, now: datetime) -> bool:
        return datetime.fromisoformat(record.expires_at_iso) <= now

    def approve(self, id: str, approver_note: str | None, executor, registry: SkillRegistry) -> PendingApproval:
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

        context = ContextPack(goal=record.context.get("goal", "approved execution"), cwd=record.context.get("cwd"))
        result = executor.execute_plan(
            Plan(goal=context.goal, steps=[record.step]),
            context=context,
            registry=registry,
            trace=None,
            approval_service=self,
            requester={"source": "approval", "approval_id": record.id, "approver_note": approver_note},
            force_execute_writes=True,
        )[0]
        record.status = "approved"
        record.result = result
        record.error = result.error
        self.memory_manager.episodic.append(
            kind="approval",
            summary=f"Approved and executed {record.step.skill_name}",
            meta={"approval_id": record.id, "step_id": record.step.id, "ok": result.ok, "approver_note": approver_note},
        )
        self._persist_or_clean(record)
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

        record.status = "rejected"
        record.error = reason
        self.memory_manager.episodic.append(
            kind="approval",
            summary=f"Rejected {record.step.skill_name}",
            meta={"approval_id": record.id, "reason": reason},
        )
        self._persist_or_clean(record)
        return record

    def cleanup_expired(self) -> int:
        return self.store.cleanup_expired(now_iso())

    def _persist_or_clean(self, record: PendingApproval) -> None:
        autoclean = os.getenv("BENJAMIN_APPROVALS_AUTOCLEAN", "on").casefold() != "off"
        if autoclean and record.status in {"approved", "rejected", "expired"}:
            self.store.delete(record.id)
        else:
            self.store.upsert(record)
