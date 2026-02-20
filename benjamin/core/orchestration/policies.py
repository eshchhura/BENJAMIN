"""Execution policies for skill steps."""

from __future__ import annotations

from core.skills.base import Skill


def requires_approval(skill: Skill) -> bool:
    """Current policy: allow read skills, block write skills."""

    return skill.side_effect == "write"
