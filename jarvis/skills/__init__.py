"""Dynamic skill discovery and base interface."""

from __future__ import annotations

import importlib
import pkgutil
from typing import Callable, List, Protocol, Any


class Skill(Protocol):
    def can_handle(intent: str) -> bool:
        ...

    def handle(request: dict) -> Any:
        ...


def load_skills() -> List[Skill]:
    """Import all modules in this package exposing the skill interface."""
    skills: List[Skill] = []
    for info in pkgutil.iter_modules(__path__):
        if info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{__name__}.{info.name}")
        if hasattr(module, "can_handle") and hasattr(module, "handle"):
            skills.append(module)  # type: ignore[arg-type]
    return skills
