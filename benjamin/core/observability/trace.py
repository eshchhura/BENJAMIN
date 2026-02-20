"""Simple trace structures for execution visibility."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field


class TraceEvent(BaseModel):
    """A timestamped event emitted during orchestration/execution."""

    ts_iso: str
    type: str
    data: dict = Field(default_factory=dict)


class Trace(BaseModel):
    """Task-level trace carrying chronological events."""

    task_id: str
    events: list[TraceEvent] = Field(default_factory=list)

    @classmethod
    def new(cls) -> "Trace":
        """Create a fresh trace with a generated task id."""

        return cls(task_id=f"task-{uuid4()}")

    def add_event(self, event_type: str, data: dict | None = None) -> None:
        """Append a structured event with current UTC timestamp."""

        self.events.append(
            TraceEvent(
                ts_iso=datetime.now(tz=timezone.utc).isoformat(),
                type=event_type,
                data=data or {},
            )
        )
