from dataclasses import dataclass

from benjamin.core.skills.base import Skill


@dataclass
class PolicyDecision:
    allowed: bool
    reason: str


class PolicyEngine:
    def evaluate(self, action: str) -> PolicyDecision:
        if "delete" in action.lower():
            return PolicyDecision(allowed=False, reason="Destructive action requires approval")
        return PolicyDecision(allowed=True, reason="Allowed")

    def requires_approval(self, skill: Skill, step_requires_approval: bool = False) -> bool:
        side_effect = getattr(skill, "side_effect", "read")
        return step_requires_approval or side_effect == "write"
