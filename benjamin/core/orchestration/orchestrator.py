"""Deterministic orchestration flow for the MVP."""

from __future__ import annotations

import logging
import os
import re

from core.observability.trace import Trace
from core.orchestration.executor import Executor
from core.orchestration.schemas import ChatResponse, ContextPack, Plan, PlanStep, UserRequest
from core.skills.builtin.filesystem import FilesystemSearchReadSkill
from core.skills.registry import SkillRegistry

logger = logging.getLogger(__name__)
_KEYWORDS = ("search", "find", "lookup")


class Orchestrator:
    """Builds context/plan, executes steps, and formats a final answer."""

    def __init__(self, registry: SkillRegistry | None = None) -> None:
        self.registry = registry or SkillRegistry()
        if "filesystem.search_read" not in self.registry.list():
            self.registry.register(FilesystemSearchReadSkill())
        self.executor = Executor(self.registry)

    def handle(self, request: UserRequest) -> ChatResponse:
        trace = Trace.new()
        ctx = ContextPack(cwd=request.cwd or os.getcwd())
        trace.add_event("RequestReceived", {"message": request.message, "cwd": ctx.cwd})

        plan = self._build_plan(request, ctx)
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

    def _build_plan(self, request: UserRequest, ctx: ContextPack) -> Plan:
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

    def _format_answer(self, results: list) -> str:
        if not results:
            return "No steps were executed."

        first = results[0]
        if not first.ok:
            return f"I couldn't complete the search: {first.error}"

        matches = (first.output or {}).get("matches", [])
        if not matches:
            return "No matching text found in files."

        lines = ["Found matches:"]
        for idx, item in enumerate(matches[:10], start=1):
            lines.append(f"{idx}. {item['path']}: {item['snippet']}")
        return "\n".join(lines)
