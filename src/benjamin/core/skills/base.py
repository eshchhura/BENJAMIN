from dataclasses import dataclass
from typing import Protocol


@dataclass
class SkillResult:
    content: str


class Skill(Protocol):
    name: str
    side_effect: str
    required_scopes: list[str]

    def run(self, query: str) -> SkillResult: ...
