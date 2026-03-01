from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import uuid4

from benjamin.core.approvals.service import ApprovalService
from benjamin.core.approvals.store import ApprovalStore
from benjamin.core.integrations.base import CalendarConnector, EmailConnector
from benjamin.core.ledger.ledger import ExecutionLedger
from benjamin.core.memory.manager import MemoryManager
from benjamin.core.observability.trace import Trace
from benjamin.core.runs.schemas import TaskRecord
from benjamin.core.runs.store import TaskStore
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
        ledger: ExecutionLedger | None = None,
    ) -> None:
        self.memory_manager = memory_manager or MemoryManager()
        self.scheduler_service = scheduler_service or SchedulerService(state_dir=self.memory_manager.state_dir)
        self.planner = Planner(llm_enabled=llm_planner_enabled)
        self.critic = PlanCritic()
        self.executor = Executor()
        self.registry = SkillRegistry()
        self.task_store = TaskStore(
            state_dir=self.memory_manager.state_dir,
            max_records=int(os.getenv("BENJAMIN_TASKS_MAX", "500")),
        )
        self.approval_service = ApprovalService(
            store=ApprovalStore(state_dir=self.memory_manager.state_dir),
            memory_manager=self.memory_manager,
            ledger=ledger,
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
        task_id = str(uuid4())
        correlation_id = str(uuid4())
        trace = Trace(task=request.message, task_id=task_id, correlation_id=correlation_id)
        trace.emit("TaskStarted", {"source": "chat"})
        memory = self.memory_manager.retrieve_context(request.message)
        trace.emit(
            "MemoryRetrieved",
            {
                "semantic_count": len(memory.get("semantic", [])),
                "episodic_count": len(memory.get("episodic", [])),
            },
        )

        context = ContextPack(goal=request.message, memory=memory, cwd=os.getcwd())
        trace.emit("PlannerStarted", {"llm_enabled": self.planner.llm_enabled})
        plan = self.planner.plan(request.message, memory=context.memory)
        trace.emit("PlannerSucceeded", {"step_count": len(plan.steps)})
        trace.emit("PlanCriticStarted", {"step_count": len(plan.steps)})
        critic_result = self.critic.review(plan)
        if not critic_result.ok:
            trace.emit(
                "PlanCriticFailed",
                {"errors": critic_result.errors, "question": critic_result.user_question},
            )
            final_response = critic_result.user_question or "I need a bit more detail before I can continue."
            result = OrchestrationResult(
                task_id=task_id,
                steps=[step.description for step in plan.steps],
                outputs=[],
                final_response=final_response,
                step_results=[],
                trace_events=trace.events,
                context=context,
            )
            self._persist_task_record(
                task_id=task_id,
                correlation_id=correlation_id,
                request=request,
                plan=plan,
                step_results=[],
                final_response=final_response,
                trace_events=trace.events,
            )
            return result

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
            requester={"source": "chat", "task_id": task_id, "correlation_id": correlation_id},
        )
        outputs = [result.output or result.error or "" for result in step_results]
        approval_errors = [
            result.error
            for result in step_results
            if result.error and result.error.startswith("approval_required:")
        ]
        if approval_errors:
            approval_id = approval_errors[0].split(":", 1)[1]
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

        trace.emit("TaskCompleted", {"step_count": len(step_results), "approval_count": len(approval_errors)})
        self._persist_task_record(
            task_id=task_id,
            correlation_id=correlation_id,
            request=request,
            plan=plan,
            step_results=step_results,
            final_response=final_response,
            trace_events=trace.events,
        )
        return OrchestrationResult(
            task_id=task_id,
            steps=plan.steps,
            outputs=outputs,
            final_response=final_response,
            step_results=step_results,
            trace_events=trace.events,
            context=context,
        )

    def _persist_task_record(
        self,
        task_id: str,
        correlation_id: str,
        request: ChatRequest,
        plan,
        step_results,
        final_response: str,
        trace_events: list[dict],
    ) -> None:
        approvals_created = []
        for result in step_results:
            if result.error and result.error.startswith("approval_required:"):
                approvals_created.append(result.error.split(":", 1)[1])

        record = TaskRecord(
            task_id=task_id,
            ts_iso=datetime.now(timezone.utc).isoformat(),
            source="chat",
            user_message=request.message,
            plan={"goal": plan.goal, "steps": [step.model_dump() for step in plan.steps]},
            step_results=[result.model_dump() for result in step_results],
            approvals_created=approvals_created,
            answer=final_response,
            trace_events=trace_events,
            correlation_id=correlation_id,
        )
        self.task_store.append(record)

    def run(self, goal: str) -> OrchestrationResult:
        return self.handle(ChatRequest(message=goal))
