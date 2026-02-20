"""Core request/response and planning schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from core.observability.trace import Trace


class UserRequest(BaseModel):
    """Incoming user payload for /chat."""

    message: str
    cwd: str | None = None


class ContextPack(BaseModel):
    """Runtime context available to skills and orchestration."""

    cwd: str


class PlanStep(BaseModel):
    """A single executable step in a plan."""

    id: str
    skill_name: str
    args: dict[str, Any] = Field(default_factory=dict)
    why: str
    requires_approval: bool = False


class Plan(BaseModel):
    """Collection of sequential plan steps."""

    steps: list[PlanStep] = Field(default_factory=list)


class StepResult(BaseModel):
    """Normalized output of one executed step."""

    step_id: str
    skill_name: str
    ok: bool
    output: dict[str, Any] | None = None
    error: str | None = None


class ChatResponse(BaseModel):
    """Final API response containing answer and execution trace."""

    answer: str
    trace: Trace
