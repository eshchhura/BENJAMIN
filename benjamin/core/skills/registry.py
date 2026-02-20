"""In-memory skill registry."""

from __future__ import annotations

from core.skills.base import Skill


class SkillRegistry:
    """Stores and resolves skills by unique name."""

    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        self._skills[skill.name] = skill

    def get(self, name: str) -> Skill:
        return self._skills[name]

    def list(self) -> list[str]:
        return sorted(self._skills.keys())
