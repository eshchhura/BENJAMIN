from core.skills.base import SkillResult


class WebSearchSkill:
    name = "web_search"

    def run(self, query: str) -> SkillResult:
        return SkillResult(content=f"Search results for: {query}")
