from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from benjamin.core.models.llm import LLM
from benjamin.core.models.prompts import task_prompt
from benjamin.core.orchestration.schemas import PlanStep


@dataclass
class Plan:
    goal: str
    steps: list[PlanStep]


class Planner:
    def __init__(self, llm_enabled: bool = False, llm: LLM | None = None) -> None:
        self.llm_enabled = llm_enabled
        self.llm = llm or LLM()

    def plan(self, goal: str, memory: dict[str, list[Any]] | None = None) -> Plan:
        if goal.startswith("reminders.create "):
            payload = goal[len("reminders.create ") :].strip()
            return Plan(
                goal=goal,
                steps=[
                    PlanStep(
                        description="Create reminder",
                        skill_name="reminders.create",
                        args=payload,
                        requires_approval=True,
                    )
                ],
            )

        if goal.startswith("calendar.create_event "):
            payload = goal[len("calendar.create_event ") :].strip()
            return Plan(
                goal=goal,
                steps=[
                    PlanStep(
                        description="Create calendar event",
                        skill_name="calendar.create_event",
                        args=payload,
                        requires_approval=True,
                    )
                ],
            )

        if goal.startswith("gmail.draft_email "):
            payload = goal[len("gmail.draft_email ") :].strip()
            return Plan(
                goal=goal,
                steps=[
                    PlanStep(
                        description="Create Gmail draft",
                        skill_name="gmail.draft_email",
                        args=payload,
                        requires_approval=True,
                    )
                ],
            )

        if self.llm_enabled:
            memory_block = self._memory_block(memory or {"semantic": [], "episodic": []})
            user_prompt = f"{task_prompt(goal)}\n\nRetrieved memory:\n{memory_block}\n\nUser goal: {goal}"
            llm_step = self.llm.complete(user_prompt)
            return Plan(
                goal=goal,
                steps=[PlanStep(description=f"Analyze: {goal}"), PlanStep(description=llm_step)],
            )

        return Plan(
            goal=goal,
            steps=[PlanStep(description=f"Analyze: {goal}"), PlanStep(description=f"Execute: {goal}")],
        )

    def _memory_block(self, memory: dict[str, list[Any]]) -> str:
        semantic = memory.get("semantic", [])
        episodic = memory.get("episodic", [])

        lines: list[str] = ["- Semantic:"]
        for fact in semantic:
            lines.append(f"  - {fact.key}: {fact.value}")

        lines.append("- Recent episodes:")
        for episode in episodic[-3:]:
            lines.append(f"  - {episode.summary}")

        block = "\n".join(lines)
        if len(block) <= 1500:
            return block
        return block[:1499].rstrip() + "…"
