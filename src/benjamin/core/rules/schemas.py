from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class RuleActionNotify(BaseModel):
    type: Literal["notify"]
    title: str
    body_template: str


class RuleActionProposeStep(BaseModel):
    type: Literal["propose_step"]
    skill_name: str
    args: dict[str, Any] = Field(default_factory=dict)
    rationale: str


RuleAction = RuleActionNotify | RuleActionProposeStep


class RuleTrigger(BaseModel):
    type: Literal["schedule", "gmail", "calendar"]
    every_minutes: int = 5
    query: str | None = None
    max_results: int = 5
    hours_ahead: int = 24


class RuleCondition(BaseModel):
    contains: str | None = None
    not_contains: str | None = None


class Rule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    enabled: bool = True
    created_at_iso: str = Field(default_factory=now_iso)
    updated_at_iso: str = Field(default_factory=now_iso)
    trigger: RuleTrigger
    condition: RuleCondition = Field(default_factory=RuleCondition)
    actions: list[RuleAction] = Field(default_factory=list)
    last_run_iso: str | None = None
    last_match_iso: str | None = None


class RuleCreate(BaseModel):
    name: str
    enabled: bool = True
    trigger: RuleTrigger
    condition: RuleCondition = Field(default_factory=RuleCondition)
    actions: list[RuleAction] = Field(default_factory=list)


class RuleRunResult(BaseModel):
    rule_id: str
    ok: bool
    matched: bool
    match_count: int
    notes: list[str] = Field(default_factory=list)
    error: str | None = None
