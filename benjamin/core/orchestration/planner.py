"""LLM-backed planner that emits validated Plan objects."""

from __future__ import annotations

from core.models.llm import LLMClient
from core.orchestration.schemas import ContextPack, Plan, UserRequest
from core.skills.registry import SkillRegistry


class Planner:
    """Create plans via an LLM and validate against known skills."""

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client or LLMClient()

    def make_plan(self, request: UserRequest, ctx: ContextPack, registry: SkillRegistry) -> Plan:
        """Generate and validate a plan. Raises on failure for caller fallback."""

        available_skills = registry.list()
        system_prompt = (
            "You are BENJAMIN planner. Return ONLY JSON matching this exact structure: "
            '{"steps":[{"id":"...","skill_name":"...","args":{},"why":"...",'
            '"requires_approval":false}]}. '
            f"Use only these skills: {', '.join(available_skills)}. "
            "Prefer minimal steps."
        )
        user_prompt = (
            f"User message: {request.message}\n"
            f"Current working directory: {ctx.cwd}\n"
            "Produce a plan now."
        )
        json_schema_hint = {
            "type": "object",
            "properties": {
                "steps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "skill_name": {"type": "string"},
                            "args": {"type": "object"},
                            "why": {"type": "string"},
                            "requires_approval": {"type": "boolean"},
                        },
                        "required": ["id", "skill_name", "args", "why", "requires_approval"],
                    },
                }
            },
            "required": ["steps"],
        }

        plan_dict = self.llm_client.complete_json(system_prompt, user_prompt, json_schema_hint)
        plan = Plan.model_validate(plan_dict)

        unknown = [step.skill_name for step in plan.steps if step.skill_name not in available_skills]
        if unknown:
            raise RuntimeError(f"Planner returned unknown skills: {unknown}")

        return plan
