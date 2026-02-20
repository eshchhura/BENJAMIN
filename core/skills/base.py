from dataclasses import dataclass
from typing import Protocol


@dataclass
class SkillResult:
    content: str


class Skill(Protocol):
    name: str

    def run(self, query: str) -> SkillResult: ...
