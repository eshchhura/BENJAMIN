from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChatRequest:
    message: str


@dataclass
class ContextPack:
    goal: str
    memory: dict[str, list[Any]] = field(default_factory=lambda: {"semantic": [], "episodic": []})


@dataclass
class OrchestrationResult:
    steps: list[str]
    outputs: list[str]
    final_response: str
    trace_events: list[dict[str, Any]] = field(default_factory=list)
    context: ContextPack | None = None
