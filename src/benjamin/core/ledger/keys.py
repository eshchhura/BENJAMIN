from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from benjamin.core.orchestration.schemas import PlanStep


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _stable_hash(parts: list[str]) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def _normalize_args(args: Any) -> Any:
    if isinstance(args, str):
        try:
            return json.loads(args)
        except json.JSONDecodeError:
            return args
    return args


def approval_execution_key(approval_id: str, step: PlanStep) -> str:
    payload = canonical_json(_normalize_args(step.args))
    return _stable_hash(["approval_exec", approval_id, step.skill_name or "", payload])


def job_run_key(job_id: str, scheduled_run_iso: str | None, extra: dict[str, Any] | None = None) -> str:
    bucket = scheduled_run_iso
    if bucket is None:
        now = datetime.now(timezone.utc)
        bucket = now.replace(second=0, microsecond=0).isoformat()
    extra_payload = canonical_json(extra or {})
    return _stable_hash(["job_run", job_id, bucket, extra_payload])


def rule_action_key(
    rule_id: str,
    action_index: int,
    item_id: str | None,
    signature: dict[str, Any],
) -> str:
    sig = canonical_json(signature)
    return _stable_hash(["rule_action", rule_id, str(action_index), item_id or "none", sig])
