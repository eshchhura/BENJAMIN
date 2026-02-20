from dataclasses import dataclass

from .executor import Executor
from .planner import Planner


@dataclass
class OrchestrationResult:
    steps: list[str]
    outputs: list[str]
    final_response: str


class Orchestrator:
    def __init__(self) -> None:
        self.planner = Planner()
        self.executor = Executor()

    def run(self, goal: str) -> OrchestrationResult:
        plan = self.planner.plan(goal)
        outputs = [self.executor.execute(step) for step in plan.steps]
        return OrchestrationResult(steps=plan.steps, outputs=outputs, final_response=outputs[-1])
