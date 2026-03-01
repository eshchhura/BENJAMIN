from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from benjamin.core.draft.drafter import Drafter
from benjamin.core.models.llm_provider import BenjaminLLM, LLMOutputError, LLMUnavailable
from benjamin.core.models.prompts import planner_system_prompt, planner_user_prompt
from benjamin.core.orchestration.schemas import PlanStep


@dataclass
class Plan:
    goal: str
    steps: list[PlanStep]


class Planner:
    def __init__(self, llm_enabled: bool = False, llm: BenjaminLLM | None = None) -> None:
        self.llm = llm or BenjaminLLM()
        self.llm_enabled = llm_enabled or BenjaminLLM.feature_enabled("BENJAMIN_LLM_PLANNER")
        self.drafter = Drafter(llm=self.llm)

    def plan(self, goal: str, memory: dict[str, list[Any]] | None = None) -> Plan:
        deterministic = self._deterministic_plan(goal)
        if deterministic is not None:
            return deterministic

        if self.llm_enabled:
            planned = self._llm_plan(goal=goal, memory=memory or {"semantic": [], "episodic": []})
            if planned is not None:
                return planned

        return Plan(
            goal=goal,
            steps=[PlanStep(description=f"Analyze: {goal}"), PlanStep(description=f"Execute: {goal}")],
        )

    def _deterministic_plan(self, goal: str) -> Plan | None:
        if goal.startswith("reminders.create "):
            payload = goal[len("reminders.create ") :].strip()
            return Plan(goal=goal, steps=[PlanStep(description="Create reminder", skill_name="reminders.create", args=payload, requires_approval=True)])

        if goal.startswith("calendar.create_event "):
            payload = goal[len("calendar.create_event ") :].strip()
            return Plan(goal=goal, steps=[PlanStep(description="Create calendar event", skill_name="calendar.create_event", args=payload, requires_approval=True)])

        if goal.startswith("gmail.draft_email "):
            payload = goal[len("gmail.draft_email ") :].strip()
            try:
                parsed = json.loads(payload)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict) and len(str(parsed.get("body") or "").strip()) < 12:
                parsed["body"] = self.drafter.draft_email(
                    to=[str(item) for item in parsed.get("to") or []],
                    subject=str(parsed.get("subject") or ""),
                    context_text=str(parsed.get("body") or "Please provide a helpful response."),
                )
                payload = json.dumps(parsed)
            return Plan(goal=goal, steps=[PlanStep(description="Create Gmail draft", skill_name="gmail.draft_email", args=payload, requires_approval=True)])
        return None

    def _llm_plan(self, goal: str, memory: dict[str, list[Any]]) -> Plan | None:
        skills = [
            {"name": "reminders.create", "description": "Create reminder", "args_schema": '{"message":"...","run_at_iso":"..."}'},
            {"name": "calendar.search", "description": "Search calendar", "args_schema": '{"query":"..."}'},
            {"name": "calendar.create_event", "description": "Create event (approval)", "args_schema": '{"title":"...","start_iso":"...","end_iso":"..."}'},
            {"name": "gmail.search", "description": "Search Gmail", "args_schema": '{"query":"..."}'},
            {"name": "gmail.read_message", "description": "Read Gmail message", "args_schema": '{"message_id":"..."}'},
            {"name": "gmail.thread_summary", "description": "Summarize thread", "args_schema": '{"thread_id":"..."}'},
            {"name": "gmail.draft_email", "description": "Draft Gmail email (approval)", "args_schema": '{"to":["a@b.com"],"subject":"...","body":"..."}'},
        ]
        valid_skills = {item["name"] for item in skills}
        prompt = planner_user_prompt(goal=goal, memory_block=self._memory_block(memory), skills=skills)
        try:
            payload = self.llm.complete_json(
                system=planner_system_prompt(),
                user=prompt,
                schema_hint={"goal": "string", "steps": "array"},
            )
            steps = []
            for raw in payload.get("steps", []):
                step = PlanStep.model_validate(raw)
                if step.skill_name and step.skill_name not in valid_skills:
                    return None
                steps.append(step)
            if not steps:
                return None
            return Plan(goal=str(payload.get("goal") or goal), steps=steps)
        except (LLMUnavailable, LLMOutputError, ValueError, TypeError):
            return None

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
