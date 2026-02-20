from benjamin.core.skills.base import SkillResult


class FilesystemSkill:
    name = "filesystem"

    def run(self, query: str) -> SkillResult:
        return SkillResult(content=f"Filesystem action: {query}")
