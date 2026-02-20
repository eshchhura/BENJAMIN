from core.skills.base import SkillResult


class RemindersSkill:
    name = "reminders"

    def run(self, query: str) -> SkillResult:
        return SkillResult(content=f"Reminder created: {query}")
