"""Deterministic orchestration flow for the MVP."""

from __future__ import annotations

import logging
import os
import re

from core.models.llm import LLMClient
from core.observability.trace import Trace
from core.orchestration.executor import Executor
from core.orchestration.planner import Planner
from core.orchestration.schemas import ChatResponse, ContextPack, Plan, PlanStep, StepResult, UserRequest
from core.skills.builtin.filesystem import FilesystemSearchReadSkill
from core.skills.builtin.web_search import WebSearchSkill
from core.skills.registry import SkillRegistry

logger = logging.getLogger(__name__)
_KEYWORDS = ("search", "find", "lookup")


class Orchestrator:
    """Builds context/plan, executes steps, and formats a final answer."""

    def __init__(self, registry: SkillRegistry | None = None) -> None:
        self.registry = registry or SkillRegistry()
        self._register_builtin_skills()
        self.executor = Executor(self.registry)
        self.llm_client = LLMClient()
        self.planner = Planner(self.llm_client)

    def _register_builtin_skills(self) -> None:
        builtins = [FilesystemSearchReadSkill(), WebSearchSkill()]
        for skill in builtins:
            if skill.name not in self.registry.list():
                self.registry.register(skill)

    def handle(self, request: UserRequest) -> ChatResponse:
        trace = Trace.new()
        ctx = ContextPack(cwd=request.cwd or os.getcwd())
        trace.add_event("RequestReceived", {"message": request.message, "cwd": ctx.cwd})

        plan = self._plan_with_fallback(request, ctx, trace)
        trace.add_event("PlanCreated", {"steps": [step.model_dump() for step in plan.steps]})

        if not plan.steps:
            answer = "I can search files. Try: ‘search <term>’"
            trace.add_event("FallbackResponse", {"answer": answer})
            return ChatResponse(answer=answer, trace=trace)

        results = self.executor.execute(plan, ctx, trace)
        answer = self._format_answer(results)
        trace.add_event("ResponseReady", {"answer": answer})
        logger.info("Finished task %s", trace.task_id)
        return ChatResponse(answer=answer, trace=trace)

    def _plan_with_fallback(self, request: UserRequest, ctx: ContextPack, trace: Trace) -> Plan:
        if self.llm_client.mode != "off":
            trace.add_event(
                "PlannerAttempted",
                {"mode": self.llm_client.mode, "message_preview": request.message[:120]},
            )
            try:
                plan = self.planner.make_plan(request, ctx, self.registry)
                if plan.steps:
                    trace.add_event("PlannerSucceeded", {"step_count": len(plan.steps)})
                    return plan
                trace.add_event("PlannerFailed", {"error": "Planner returned empty plan"})
            except Exception as exc:  # noqa: BLE001 - intentional fallback safety.
                logger.exception("LLM planner failed, using deterministic plan")
                trace.add_event("PlannerFailed", {"error": str(exc)})

        return self._build_keyword_plan(request, ctx)

    def _build_keyword_plan(self, request: UserRequest, ctx: ContextPack) -> Plan:
        message = request.message.strip()
        lower = message.lower()
        keyword = next((k for k in _KEYWORDS if k in lower), None)
        if not keyword:
            return Plan(steps=[])

        query = re.sub(rf"\b{re.escape(keyword)}\b", "", message, count=1, flags=re.IGNORECASE).strip()
        query = query or message

        step = PlanStep(
            id="step-1",
            skill_name="filesystem.search_read",
            args={"query": query, "cwd": ctx.cwd, "max_results": 10},
            why="User asked to search/find content in files",
        )
        return Plan(steps=[step])

    def _format_answer(self, results: list[StepResult]) -> str:
        if not results:
            return "No steps were executed."

        first = results[0]
        if not first.ok:
            return f"I couldn't complete the search: {first.error}"

        if first.skill_name == "web.search":
            reason = (first.output or {}).get("reason", "web.search is not implemented yet")
            return f"Web search is currently unavailable: {reason}"

        matches = (first.output or {}).get("matches", [])
        if not matches:
            return "No matching text found in files."

        lines = ["Found matches:"]
        for idx, item in enumerate(matches[:10], start=1):
            lines.append(f"{idx}. {item['path']}: {item['snippet']}")
        return "\n".join(lines)
