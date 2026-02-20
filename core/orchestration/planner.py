from dataclasses import dataclass


@dataclass
class Plan:
    goal: str
    steps: list[str]


class Planner:
    def plan(self, goal: str) -> Plan:
        return Plan(goal=goal, steps=[f"Analyze: {goal}", f"Execute: {goal}"])
