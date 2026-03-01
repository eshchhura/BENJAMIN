from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class LedgerRecord(BaseModel):
    key: str
    kind: Literal["approval_exec", "job_run", "rule_action"]
    status: Literal["started", "succeeded", "skipped", "failed"]
    ts_iso: str
    correlation_id: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)
