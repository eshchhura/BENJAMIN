from pydantic import BaseModel

from core.orchestration.schemas import ContextPack
from core.skills.base import Skill
from core.skills.registry import SkillRegistry


class DummyIn(BaseModel):
    x: int


class DummyOut(BaseModel):
    y: int


class DummySkill(Skill):
    name = "dummy.skill"
    description = "dummy"
    input_model = DummyIn
    output_model = DummyOut

    def run(self, input_data: DummyIn, ctx: ContextPack) -> DummyOut:
        return DummyOut(y=input_data.x + 1)


def test_registry_register_get_list() -> None:
    registry = SkillRegistry()
    skill = DummySkill()

    registry.register(skill)

    assert registry.get("dummy.skill") is skill
    assert registry.list() == ["dummy.skill"]
