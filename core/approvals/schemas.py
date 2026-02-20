from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from core.orchestration.schemas import PlanStep, StepResult


class PendingApproval(BaseModel):
    id: str
    created_at_iso: str
    expires_at_iso: str
    status: Literal["pending", "approved", "rejected", "expired"]
    requester: dict[str, Any] = Field(default_factory=dict)
    step: PlanStep
    context: dict[str, Any] = Field(default_factory=dict)
    rationale: str
    result: StepResult | None = None
    error: str | None = None


class ApproveRequest(BaseModel):
    approver_note: str | None = None


class RejectRequest(BaseModel):
    reason: str | None = None


class ApprovalListResponse(BaseModel):
    approvals: list[PendingApproval]
