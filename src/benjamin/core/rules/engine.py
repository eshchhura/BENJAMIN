from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from benjamin.core.approvals.service import ApprovalService
from benjamin.core.memory.manager import MemoryManager
from benjamin.core.orchestration.schemas import ContextPack, PlanStep
from benjamin.core.skills.registry import SkillRegistry

from .schemas import Rule, RuleActionNotify, RuleActionProposeStep, RuleRunResult


class RuleEngine:
    def __init__(
        self,
        memory_manager: MemoryManager,
        approval_service: ApprovalService,
        registry: SkillRegistry,
        notifier,
        email_connector=None,
        calendar_connector=None,
    ) -> None:
        self.memory_manager = memory_manager
        self.approval_service = approval_service
        self.registry = registry
        self.notifier = notifier
        self.email_connector = email_connector
        self.calendar_connector = calendar_connector

    def evaluate_rule(self, rule: Rule, ctx: dict | None = None) -> RuleRunResult:
        del ctx
        now = datetime.now(timezone.utc).isoformat()
        notes: list[str] = []
        try:
            results = self._load_trigger_results(rule)
            blob = self._build_blob(results)
            matched = self._matches(rule, blob)
            count = len(results)
            notes.append(f"trigger_count={count}")

            if matched:
                for action in rule.actions:
                    if isinstance(action, RuleActionNotify):
                        body = self._render_notify(action.body_template, count=count, blob=blob, now_iso=now)
                        self.notifier.send(title=action.title, body=body, meta={"rule_id": rule.id})
                        notes.append("notify_sent")
                    elif isinstance(action, RuleActionProposeStep):
                        step = PlanStep(
                            description=f"Rule action for {action.skill_name}",
                            skill_name=action.skill_name,
                            args=json.dumps(action.args),
                            requires_approval=True,
                        )
                        self.approval_service.create_pending(
                            step=step,
                            ctx=ContextPack(goal=f"Rule matched: {rule.name}", cwd=None),
                            requester={"source": "rule", "rule_id": rule.id},
                            rationale=action.rationale,
                            registry=self.registry,
                        )
                        notes.append("approval_created")

            self.memory_manager.episodic.append(
                kind="rule",
                summary=f"Ran rule {rule.name}: matched={matched} count={count}",
                meta={"rule_id": rule.id, "trigger_type": rule.trigger.type},
            )
            return RuleRunResult(rule_id=rule.id, ok=True, matched=matched, match_count=count, notes=notes)
        except Exception as exc:
            self.memory_manager.episodic.append(
                kind="rule",
                summary=f"Rule {rule.name} failed",
                meta={"rule_id": rule.id, "error": str(exc)},
            )
            return RuleRunResult(rule_id=rule.id, ok=False, matched=False, match_count=0, notes=notes, error=str(exc))

    def _load_trigger_results(self, rule: Rule) -> list[dict]:
        trigger = rule.trigger
        if trigger.type == "schedule":
            return [{"title": "heartbeat", "snippet": "scheduler tick"}]
        if trigger.type == "gmail":
            if self.email_connector is None:
                return []
            return self.email_connector.search_messages(query=trigger.query or "", max_results=trigger.max_results)
        if trigger.type == "calendar":
            if self.calendar_connector is None:
                return []
            now = datetime.now(timezone.utc)
            return self.calendar_connector.search_events(
                calendar_id="primary",
                time_min_iso=now.isoformat(),
                time_max_iso=(now + timedelta(hours=trigger.hours_ahead)).isoformat(),
                query=trigger.query,
                max_results=trigger.max_results,
            )
        return []

    def _build_blob(self, results: list[dict]) -> str:
        chunks: list[str] = []
        for item in results:
            chunks.extend(
                [
                    str(item.get("subject", "")),
                    str(item.get("snippet", "")),
                    str(item.get("title", "")),
                    str(item.get("summary", "")),
                ]
            )
        return "\n".join([chunk for chunk in chunks if chunk]).casefold()

    def _matches(self, rule: Rule, blob: str) -> bool:
        if rule.condition.contains and rule.condition.contains.casefold() not in blob:
            return False
        if rule.condition.not_contains and rule.condition.not_contains.casefold() in blob:
            return False
        return True

    def _render_notify(self, template: str, count: int, blob: str, now_iso: str) -> str:
        top1 = blob.splitlines()[0] if blob else ""
        rendered = template
        replacements = {
            "{{count}}": str(count),
            "{{top1}}": top1,
            "{{now_iso}}": now_iso,
        }
        for key, value in replacements.items():
            rendered = rendered.replace(key, value)
        return rendered
