from benjamin.core.security.scopes import default_scopes_for_skill
from benjamin.core.skills.base import Skill


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        if not hasattr(skill, "side_effect"):
            setattr(skill, "side_effect", "read")
        scopes = list(getattr(skill, "required_scopes", []) or [])
        if not scopes:
            scopes = default_scopes_for_skill(skill.name, getattr(skill, "side_effect", "read"))
            setattr(skill, "required_scopes", scopes)
        self._skills[skill.name] = skill

    def get(self, name: str) -> Skill:
        return self._skills[name]

    def names(self) -> list[str]:
        return sorted(self._skills.keys())
