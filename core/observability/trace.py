from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Trace:
    task: str
    steps: list[str] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)

    def add_step(self, step: str) -> None:
        self.steps.append(step)

    def emit(self, name: str, payload: dict[str, Any]) -> None:
        self.events.append({"event": name, "payload": payload})
