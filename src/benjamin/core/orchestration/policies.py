from dataclasses import dataclass

from benjamin.core.security.policy import PermissionsPolicy
from benjamin.core.skills.base import Skill


@dataclass
class PolicyDecision:
    allowed: bool
    reason: str


class PolicyEngine:
    def __init__(self, permissions_policy: PermissionsPolicy | None = None) -> None:
        self.permissions_policy = permissions_policy or PermissionsPolicy()

    def evaluate(self, action: str) -> PolicyDecision:
        if "delete" in action.lower():
            return PolicyDecision(allowed=False, reason="Destructive action requires approval")
        return PolicyDecision(allowed=True, reason="Allowed")

    def requires_approval(self, skill: Skill, step_requires_approval: bool = False) -> bool:
        side_effect = getattr(skill, "side_effect", "read")
        return step_requires_approval or side_effect == "write"

    def required_scopes(self, skill: Skill) -> list[str]:
        return list(getattr(skill, "required_scopes", []) or [])

    def check_skill_scopes(self, skill: Skill) -> tuple[bool, list[str]]:
        return self.permissions_policy.check_scopes(self.required_scopes(skill))
