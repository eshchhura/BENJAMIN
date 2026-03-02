from __future__ import annotations

import json

from benjamin.core.orchestration.policies import PolicyEngine
from benjamin.core.orchestration.schemas import ContextPack, PlanStep, StepResult
from benjamin.core.ops.safe_mode import is_safe_mode_enabled
from benjamin.core.security.audit import log_policy_event


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
            policy = self.policy_engine.permissions_policy.__class__()
            skill = registry.get(step.skill_name)
            required_scopes = self.policy_engine.required_scopes(skill)
            scopes_ok, disabled_scopes = policy.check_scopes(required_scopes)
            correlation_id = str(requester.get("correlation_id") or "")
            source = str(requester.get("source") or "chat")
            if not scopes_ok:
                if trace is not None:
                    trace.emit(
                        "PolicyDenied",
                        {
                            "step_id": step.id,
                            "skill_name": step.skill_name,
                            "required_scopes": required_scopes,
                            "decision_reason": "scope_disabled",
                            "disabled_scopes": disabled_scopes,
                            "policy_snapshot_summary": policy.snapshot(),
                        },
                    )
                log_policy_event(
                    approval_service.memory_manager,
                    correlation_id=correlation_id,
                    source=source,
                    decision="denied",
                    skill_name=step.skill_name,
                    required_scopes=required_scopes,
                    snapshot=policy.snapshot_model(),
                    reason="scope_disabled",
                    extra_meta={
                        "task_id": str(requester.get("task_id") or ""),
                        "approval_id": str(requester.get("approval_id") or ""),
                    },
                )
                return StepResult(step_id=step.id, ok=False, error=f"policy_denied:{','.join(disabled_scopes)}")

            log_policy_event(
                approval_service.memory_manager,
                correlation_id=correlation_id,
                source=source,
                decision="allowed",
                skill_name=step.skill_name,
                required_scopes=required_scopes,
                snapshot=policy.snapshot_model(),
                reason="allowed",
                extra_meta={
                    "task_id": str(requester.get("task_id") or ""),
                    "approval_id": str(requester.get("approval_id") or ""),
                },
            )

            requires_approval = self.policy_engine.requires_approval(skill, step_requires_approval=step.requires_approval)
            if getattr(skill, "side_effect", "read") == "write" and is_safe_mode_enabled(approval_service.memory_manager.state_dir):
                if trace is not None:
                    trace.emit(
                        "SafeModeDenied",
                        {
                            "step_id": step.id,
                            "skill_name": step.skill_name,
                            "required_scopes": required_scopes,
                        },
                    )
                return StepResult(step_id=step.id, ok=False, error="safe_mode_denied")

            if requires_approval and not force_execute_writes:
                payload = self._approval_payload(step)
                approval = approval_service.create_pending(
                    step=step,
                    ctx=context,
                    requester=requester,
                    rationale=payload,
                    registry=registry,
                    required_scopes=required_scopes,
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

            try:
                result = skill.run(step.args)
            except Exception as exc:
                return StepResult(step_id=step.id, ok=False, error=str(exc))
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
