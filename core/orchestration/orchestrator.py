from __future__ import annotations

from core.memory.manager import MemoryManager
from core.observability.trace import Trace
from core.scheduler.scheduler import SchedulerService
from core.skills.builtin.briefings import BriefingsDailySkill
from core.skills.builtin.reminders import RemindersCreateSkill
from core.skills.registry import SkillRegistry

from .executor import Executor
from .planner import Planner
from .schemas import ChatRequest, ContextPack, OrchestrationResult


class Orchestrator:
    def __init__(
        self,
        memory_manager: MemoryManager | None = None,
        llm_planner_enabled: bool = False,
        scheduler_service: SchedulerService | None = None,
    ) -> None:
        self.memory_manager = memory_manager or MemoryManager()
        self.scheduler_service = scheduler_service or SchedulerService(state_dir=self.memory_manager.state_dir)
        self.planner = Planner(llm_enabled=llm_planner_enabled)
        self.executor = Executor()
        self.registry = SkillRegistry()
        self.registry.register(RemindersCreateSkill(self.scheduler_service, str(self.memory_manager.state_dir)))
        self.registry.register(BriefingsDailySkill(str(self.memory_manager.state_dir)))

    def handle(self, request: ChatRequest) -> OrchestrationResult:
        trace = Trace(task=request.message)
        memory = self.memory_manager.retrieve_context(request.message)
        trace.emit(
            "MemoryRetrieved",
            {
                "semantic_count": len(memory.get("semantic", [])),
                "episodic_count": len(memory.get("episodic", [])),
            },
        )

        context = ContextPack(goal=request.message, memory=memory)
        plan = self.planner.plan(request.message, memory=context.memory)
        outputs = [self.executor.execute(step) for step in plan.steps]
        final_response = outputs[-1]

        if self.memory_manager.autowrite_enabled:
            proposal = self.memory_manager.propose_writes(request.message, final_response)
            trace.emit(
                "MemoryWriteProposed",
                {
                    "semantic_count": len(proposal.get("semantic_upserts", [])),
                    "episodic_count": len(proposal.get("episodes", [])),
                },
            )
            committed = self.memory_manager.commit(proposal)
            trace.emit("MemoryWriteCommitted", committed)

        return OrchestrationResult(
            steps=plan.steps,
            outputs=outputs,
            final_response=final_response,
            trace_events=trace.events,
            context=context,
        )

    def run(self, goal: str) -> OrchestrationResult:
        return self.handle(ChatRequest(message=goal))
