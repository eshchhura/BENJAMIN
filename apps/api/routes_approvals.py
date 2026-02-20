from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query

from core.approvals.schemas import ApprovalListResponse, ApproveRequest, PendingApproval, RejectRequest
from core.approvals.service import ApprovalService
from core.orchestration.orchestrator import Orchestrator

from .deps import get_approval_service, get_orchestrator

router = APIRouter()


@router.get("", response_model=ApprovalListResponse)
def list_approvals(
    status: Literal["pending", "approved", "rejected", "expired"] | None = Query(default=None),
    service: ApprovalService = Depends(get_approval_service),
) -> ApprovalListResponse:
    service.cleanup_expired()
    return ApprovalListResponse(approvals=service.store.list_all(status=status))


@router.post("/{approval_id}/approve", response_model=PendingApproval)
def approve_approval(
    approval_id: str,
    request: ApproveRequest,
    service: ApprovalService = Depends(get_approval_service),
    orchestrator: Orchestrator = Depends(get_orchestrator),
) -> PendingApproval:
    return service.approve(
        id=approval_id,
        approver_note=request.approver_note,
        executor=orchestrator.executor,
        registry=orchestrator.registry,
    )


@router.post("/{approval_id}/reject", response_model=PendingApproval)
def reject_approval(
    approval_id: str,
    request: RejectRequest,
    service: ApprovalService = Depends(get_approval_service),
) -> PendingApproval:
    return service.reject(id=approval_id, reason=request.reason)
