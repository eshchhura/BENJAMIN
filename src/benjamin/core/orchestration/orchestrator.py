from __future__ import annotations

import os

from benjamin.core.approvals.service import ApprovalService
from benjamin.core.approvals.store import ApprovalStore
from benjamin.core.integrations.base import CalendarConnector, EmailConnector
from benjamin.core.memory.manager import MemoryManager
from benjamin.core.observability.trace import Trace
from benjamin.core.scheduler.scheduler import SchedulerService
from benjamin.core.skills.builtin.briefings import BriefingsDailySkill
from benjamin.core.skills.builtin.calendar_read import CalendarSearchSkill
from benjamin.core.skills.builtin.calendar_write import CalendarCreateEventSkill
from benjamin.core.skills.builtin.gmail_read import GmailReadMessageSkill, GmailSearchSkill, GmailThreadSummarySkill
from benjamin.core.skills.builtin.gmail_write import GmailDraftEmailSkill
from benjamin.core.skills.builtin.reminders import RemindersCreateSkill
from benjamin.core.skills.registry import SkillRegistry

from .critic import PlanCritic
from .executor import Executor
from .planner import Planner
from .schemas import ChatRequest, ContextPack, OrchestrationResult


class Orchestrator:
    def __init__(
        self,
        memory_manager: MemoryManager | None = None,
        llm_planner_enabled: bool = False,
        scheduler_service: SchedulerService | None = None,
        calendar_connector: CalendarConnector | None = None,
        email_connector: EmailConnector | None = None,
    ) -> None:
        self.memory_manager = memory_manager or MemoryManager()
        self.scheduler_service = scheduler_service or SchedulerService(state_dir=self.memory_manager.state_dir)
        self.planner = Planner(llm_enabled=llm_planner_enabled)
        self.critic = PlanCritic()
        self.executor = Executor()
        self.registry = SkillRegistry()
        self.approval_service = ApprovalService(
            store=ApprovalStore(state_dir=self.memory_manager.state_dir),
            memory_manager=self.memory_manager,
        )
        self.registry.register(RemindersCreateSkill(self.scheduler_service, str(self.memory_manager.state_dir)))
        self.registry.register(BriefingsDailySkill(str(self.memory_manager.state_dir)))
        self.registry.register(CalendarSearchSkill(calendar_connector))
        self.registry.register(GmailSearchSkill(email_connector))
        self.registry.register(GmailReadMessageSkill(email_connector))
        self.registry.register(GmailThreadSummarySkill(email_connector))
        self.registry.register(CalendarCreateEventSkill(calendar_connector))
        self.registry.register(GmailDraftEmailSkill(email_connector))

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

        context = ContextPack(goal=request.message, memory=memory, cwd=os.getcwd())
        plan = self.planner.plan(request.message, memory=context.memory)
        trace.emit("PlanCriticStarted", {"step_count": len(plan.steps)})
        critic_result = self.critic.review(plan)
        if not critic_result.ok:
            trace.emit(
                "PlanCriticFailed",
                {"errors": critic_result.errors, "question": critic_result.user_question},
            )
            final_response = critic_result.user_question or "I need a bit more detail before I can continue."
            return OrchestrationResult(
                steps=[step.description for step in plan.steps],
                outputs=[],
                final_response=final_response,
                step_results=[],
                trace_events=trace.events,
                context=context,
            )

        for normalization in critic_result.normalizations:
            trace.emit(
                "PlanNormalized",
                {
                    "step_id": normalization.step_id,
                    "changes": normalization.changes,
                },
            )
        trace.emit("PlanCriticPassed", {"warnings_count": len(critic_result.warnings)})

        step_results = self.executor.execute_plan(
            plan,
            context=context,
            registry=self.registry,
            trace=trace,
            approval_service=self.approval_service,
            requester={"source": "chat", "task_id": request.message},
        )
        outputs = [result.output or result.error or "" for result in step_results]
        approval_error = next((result.error for result in step_results if result.error and result.error.startswith("approval_required:")), None)
        if approval_error:
            approval_id = approval_error.split(":", 1)[1]
            final_response = (
                f"Approval required to proceed. Approval ID: {approval_id}. "
                "Use GET /approvals and POST /approvals/{id}/approve to continue."
            )
        else:
            final_response = outputs[-1] if outputs else ""

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
            step_results=step_results,
            trace_events=trace.events,
            context=context,
        )

    def run(self, goal: str) -> OrchestrationResult:
        return self.handle(ChatRequest(message=goal))
