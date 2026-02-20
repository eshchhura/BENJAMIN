"""Sequential plan executor with policy checks and tracing."""

from __future__ import annotations

import logging

from core.observability.trace import Trace
from core.orchestration import policies
from core.orchestration.schemas import ContextPack, Plan, StepResult
from core.skills.registry import SkillRegistry

logger = logging.getLogger(__name__)


class Executor:
    """Executes plan steps in order using the skill registry."""

    def __init__(self, registry: SkillRegistry) -> None:
        self.registry = registry

    def execute(self, plan: Plan, ctx: ContextPack, trace: Trace) -> list[StepResult]:
        results: list[StepResult] = []

        for step in plan.steps:
            trace.add_event(
                "StepStarted",
                {"step_id": step.id, "skill_name": step.skill_name},
            )
            logger.info("Starting step %s (%s)", step.id, step.skill_name)

            try:
                skill = self.registry.get(step.skill_name)
                step.requires_approval = policies.requires_approval(skill)
                if step.requires_approval:
                    msg = "Step blocked by policy: write skill requires approval"
                    result = StepResult(
                        step_id=step.id,
                        skill_name=step.skill_name,
                        ok=False,
                        error=msg,
                    )
                    trace.add_event(
                        "StepFailed",
                        {"step_id": step.id, "skill_name": step.skill_name, "error": msg},
                    )
                    results.append(result)
                    continue

                output_model = skill.execute(step.args, ctx)
                result = StepResult(
                    step_id=step.id,
                    skill_name=step.skill_name,
                    ok=True,
                    output=output_model.model_dump(),
                )
                trace.add_event(
                    "StepFinished",
                    {"step_id": step.id, "skill_name": step.skill_name},
                )
                results.append(result)
            except Exception as exc:  # noqa: BLE001 - normalize all step failures.
                logger.exception("Step failed: %s", step.id)
                result = StepResult(
                    step_id=step.id,
                    skill_name=step.skill_name,
                    ok=False,
                    error=str(exc),
                )
                trace.add_event(
                    "StepFailed",
                    {"step_id": step.id, "skill_name": step.skill_name, "error": str(exc)},
                )
                results.append(result)

        return results
