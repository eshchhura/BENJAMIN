from core.skills.base import SkillResult


class CalendarReadSkill:
    name = "calendar_read"

    def run(self, query: str) -> SkillResult:
        return SkillResult(content=f"Calendar lookup for: {query}")
