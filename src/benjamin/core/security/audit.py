from __future__ import annotations

from typing import Any

from benjamin.core.memory.manager import MemoryManager
from benjamin.core.security.policy import PolicySnapshot


def _bounded(values: list[str], max_items: int = 64) -> list[str]:
    if len(values) <= max_items:
        return values
    return values[:max_items] + [f"...(+{len(values) - max_items} more)"]


def log_policy_event(
    memory_manager: MemoryManager,
    *,
    correlation_id: str,
    source: str,
    decision: str,
    skill_name: str,
    required_scopes: list[str],
    snapshot: PolicySnapshot,
    reason: str,
    extra_meta: dict[str, Any] | None = None,
) -> None:
    meta = {
        "correlation_id": correlation_id,
        "source": source,
        "decision": decision,
        "required_scopes": sorted(required_scopes),
        "enabled_scopes": _bounded(snapshot.scopes_enabled),
        "rules_allowed_scopes": _bounded(snapshot.rules_allowed_scopes),
        "skill_name": skill_name,
        "reason": reason,
    }
    if extra_meta:
        meta.update(extra_meta)

    memory_manager.episodic.append(
        kind="policy",
        summary=f"Policy {decision} for {skill_name}",
        meta=meta,
    )
