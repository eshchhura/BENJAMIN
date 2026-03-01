from __future__ import annotations

from benjamin.core.models.llm_provider import BenjaminLLM, LLMOutputError, LLMUnavailable
from benjamin.core.rules.schemas import RuleActionProposeStep, RuleCreate


class RuleNLBuilder:
    def __init__(self, llm: BenjaminLLM | None = None) -> None:
        self.llm = llm or BenjaminLLM()
        self.enabled = BenjaminLLM.feature_enabled("BENJAMIN_LLM_RULE_BUILDER")

    def from_text(self, text: str, known_write_skills: set[str] | None = None) -> RuleCreate:
        if not self.enabled:
            raise LLMUnavailable("rule builder disabled")
        payload = self.llm.complete_json(
            system="Convert user text into deterministic RuleCreate JSON.",
            user=(
                f"Input: {text}\n"
                "Allowed triggers: schedule|gmail|calendar. "
                "Actions are notify or propose_step. "
                "propose_step must target write skills only and only propose approval."
            ),
            schema_hint={"name": "string", "trigger": {"type": "schedule|gmail|calendar"}, "actions": []},
        )
        rule = RuleCreate.model_validate(payload)
        self._validate_actions(rule, known_write_skills or set())
        return rule

    def _validate_actions(self, rule: RuleCreate, known_write_skills: set[str]) -> None:
        for action in rule.actions:
            if isinstance(action, RuleActionProposeStep):
                if action.skill_name not in known_write_skills:
                    raise LLMOutputError(f"unknown write skill: {action.skill_name}")
