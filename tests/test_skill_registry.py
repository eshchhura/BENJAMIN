from benjamin.core.skills.builtin.web_search import WebSearchSkill
from benjamin.core.skills.registry import SkillRegistry


def test_skill_registry_registers_and_fetches() -> None:
    registry = SkillRegistry()
    registry.register(WebSearchSkill())

    assert registry.names() == ["web_search"]
    assert registry.get("web_search").run("python").content
