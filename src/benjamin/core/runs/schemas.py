from __future__ import annotations

from pydantic import BaseModel, Field


class TaskRecord(BaseModel):
    task_id: str
    ts_iso: str
    source: str = "chat"
    user_message: str
    plan: dict = Field(default_factory=dict)
    step_results: list[dict] = Field(default_factory=list)
    approvals_created: list[str] = Field(default_factory=list)
    answer: str
    trace_events: list[dict] = Field(default_factory=list)
    correlation_id: str
