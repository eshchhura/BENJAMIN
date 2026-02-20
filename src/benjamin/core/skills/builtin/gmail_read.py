from benjamin.core.skills.base import SkillResult


class GmailReadSkill:
    name = "gmail_read"

    def run(self, query: str) -> SkillResult:
        return SkillResult(content=f"Gmail lookup for: {query}")
