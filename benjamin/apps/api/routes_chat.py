"""Chat API routes."""

from __future__ import annotations

from fastapi import APIRouter

from core.orchestration.orchestrator import Orchestrator
from core.orchestration.schemas import ChatResponse, UserRequest

router = APIRouter()
_orchestrator = Orchestrator()


@router.post("/chat", response_model=ChatResponse)
def chat(request: UserRequest) -> ChatResponse:
    """Execute chat request through deterministic orchestrator."""

    return _orchestrator.handle(request)
