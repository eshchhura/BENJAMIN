from __future__ import annotations

import json

from core.orchestration.policies import PolicyEngine
from core.orchestration.schemas import ContextPack, PlanStep, StepResult


class Executor:
    def __init__(self, policy_engine: PolicyEngine | None = None) -> None:
        self.policy_engine = policy_engine or PolicyEngine()

    def execute_step(
        self,
        step: PlanStep,
        *,
        context: ContextPack,
        registry,
        trace,
        approval_service,
        requester: dict,
        force_execute_writes: bool = False,
    ) -> StepResult:
        if step.skill_name:
            skill = registry.get(step.skill_name)
            requires_approval = self.policy_engine.requires_approval(skill, step_requires_approval=step.requires_approval)
            if requires_approval and not force_execute_writes:
                payload = self._approval_payload(step)
                approval = approval_service.create_pending(
                    step=step,
                    ctx=context,
                    requester=requester,
                    rationale=payload,
                    registry=registry,
                )
                if trace is not None:
                    trace.emit(
                        "ApprovalRequired",
                        {
                            "approval_id": approval.id,
                            "step_id": step.id,
                            "skill_name": step.skill_name,
                            "rationale": approval.rationale,
                        },
                    )
                return StepResult(step_id=step.id, ok=False, error=f"approval_required:{approval.id}")

            result = skill.run(step.args)
            return StepResult(step_id=step.id, ok=True, output=result.content)

        return StepResult(step_id=step.id, ok=True, output=f"done:{step.description}")

    def execute_plan(
        self,
        plan,
        *,
        context: ContextPack,
        registry,
        trace,
        approval_service,
        requester: dict,
        force_execute_writes: bool = False,
    ) -> list[StepResult]:
        results: list[StepResult] = []
        for step in plan.steps:
            results.append(
                self.execute_step(
                    step,
                    context=context,
                    registry=registry,
                    trace=trace,
                    approval_service=approval_service,
                    requester=requester,
                    force_execute_writes=force_execute_writes,
                )
            )
        return results

    def _approval_payload(self, step: PlanStep) -> str:
        if step.skill_name != "reminders.create":
            return f"This action will execute {step.skill_name}."
        try:
            payload = json.loads(step.args)
        except json.JSONDecodeError:
            return "This action will create a reminder."
        message = payload.get("message", "")
        run_at_iso = payload.get("run_at_iso", "")
        return f"This action will create a reminder scheduled at {run_at_iso} with message '{message}'."
