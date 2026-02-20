from dataclasses import dataclass


@dataclass
class PolicyDecision:
    allowed: bool
    reason: str


class PolicyEngine:
    def evaluate(self, action: str) -> PolicyDecision:
        if "delete" in action.lower():
            return PolicyDecision(allowed=False, reason="Destructive action requires approval")
        return PolicyDecision(allowed=True, reason="Allowed")
