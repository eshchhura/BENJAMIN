from dataclasses import dataclass, field


@dataclass
class Trace:
    task: str
    steps: list[str] = field(default_factory=list)

    def add_step(self, step: str) -> None:
        self.steps.append(step)
