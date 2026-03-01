from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class PlanStep(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    description: str
    skill_name: str | None = None
    args: str = ""
    requires_approval: bool = False


class StepResult(BaseModel):
    step_id: str
    ok: bool
    output: str | None = None
    error: str | None = None


class CriticNormalization(BaseModel):
    step_id: str
    changes: dict[str, dict[str, Any]] = Field(default_factory=dict)


class CriticResult(BaseModel):
    ok: bool
    plan: Any | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    user_question: str | None = None
    normalizations: list[CriticNormalization] = Field(default_factory=list)


@dataclass
class ChatRequest:
    message: str


@dataclass
class ContextPack:
    goal: str
    memory: dict[str, list[Any]] = field(default_factory=lambda: {"semantic": [], "episodic": []})
    cwd: str | None = None


@dataclass
class OrchestrationResult:
    steps: list[str]
    outputs: list[str]
    final_response: str
    step_results: list[StepResult] = field(default_factory=list)
    trace_events: list[dict[str, Any]] = field(default_factory=list)
    context: ContextPack | None = None
    task_id: str | None = None
