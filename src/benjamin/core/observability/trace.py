from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Trace:
    task: str
    task_id: str | None = None
    correlation_id: str | None = None
    steps: list[str] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)

    def add_step(self, step: str) -> None:
        self.steps.append(step)

    def emit(self, name: str, payload: dict[str, Any]) -> None:
        enriched_payload = dict(payload)
        if self.task_id:
            enriched_payload.setdefault("task_id", self.task_id)
        if self.correlation_id:
            enriched_payload.setdefault("correlation_id", self.correlation_id)
        self.events.append({"event": name, "payload": enriched_payload})
