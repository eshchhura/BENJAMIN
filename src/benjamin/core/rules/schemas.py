from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


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


class RuleMatchItem(BaseModel):
    item_id: str
    ts_iso: str | None = None
    text: str
    raw: dict[str, Any] = Field(default_factory=dict)


class PlannedActionNotify(BaseModel):
    type: Literal["notify"]
    title: str
    body: str


class PlannedActionProposeStep(BaseModel):
    type: Literal["propose_step"]
    skill_name: str
    args: dict[str, Any] = Field(default_factory=dict)
    rationale: str
    would_create_approval: bool = True


RulePlannedAction = PlannedActionNotify | PlannedActionProposeStep


class RuleTestPreview(BaseModel):
    rule_id: str | None = None
    rule_name: str | None = None
    matched: bool
    match_count: int
    candidate_count: int
    matching_items: list[RuleMatchItem] = Field(default_factory=list)
    planned_actions: list[RulePlannedAction] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class RuleTrigger(BaseModel):
    type: Literal["schedule", "gmail", "calendar"]
    every_minutes: int = 5
    query: str | None = None
    max_results: int = 5
    hours_ahead: int = 24


class RuleCondition(BaseModel):
    contains: str | None = None
    not_contains: str | None = None


class RuleState(BaseModel):
    last_run_iso: str | None = None
    last_match_iso: str | None = None
    cooldown_until_iso: str | None = None
    seen_ids: list[str] = Field(default_factory=list)
    seen_ids_max: int = 200
    last_cursor_iso: str | None = None


class Rule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    enabled: bool = True
    created_at_iso: str = Field(default_factory=now_iso)
    updated_at_iso: str = Field(default_factory=now_iso)
    trigger: RuleTrigger
    condition: RuleCondition = Field(default_factory=RuleCondition)
    actions: list[RuleAction] = Field(default_factory=list)
    max_actions_per_run: int = 3
    cooldown_minutes: int = 0
    state: RuleState = Field(default_factory=RuleState)

    # Deprecated top-level fields preserved for backward compatibility.
    last_run_iso: str | None = None
    last_match_iso: str | None = None

    @model_validator(mode="after")
    def migrate_legacy_state(self) -> "Rule":
        state_updates: dict[str, str] = {}
        if self.last_run_iso and not self.state.last_run_iso:
            state_updates["last_run_iso"] = self.last_run_iso
        if self.last_match_iso and not self.state.last_match_iso:
            state_updates["last_match_iso"] = self.last_match_iso
        if state_updates:
            self.state = self.state.model_copy(update=state_updates)
        return self


class RuleCreate(BaseModel):
    name: str
    enabled: bool = True
    trigger: RuleTrigger
    condition: RuleCondition = Field(default_factory=RuleCondition)
    actions: list[RuleAction] = Field(default_factory=list)
    max_actions_per_run: int = 3
    cooldown_minutes: int = 0


class RuleRunResult(BaseModel):
    rule_id: str
    ok: bool
    matched: bool
    match_count: int
    notes: list[str] = Field(default_factory=list)
    error: str | None = None
