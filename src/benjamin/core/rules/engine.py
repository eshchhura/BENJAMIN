from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from benjamin.core.approvals.service import ApprovalService
from benjamin.core.memory.manager import MemoryManager
from benjamin.core.orchestration.schemas import ContextPack, PlanStep
from benjamin.core.skills.registry import SkillRegistry

from .schemas import Rule, RuleActionNotify, RuleActionProposeStep, RuleRunResult, now_iso


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
        notes: list[str] = []
        state = rule.state
        now = datetime.now(timezone.utc)
        state.last_run_iso = now.isoformat()

        try:
            if self._is_cooldown_active(rule, now):
                notes.append("cooldown_active")
                self._sync_legacy_state(rule)
                return RuleRunResult(rule_id=rule.id, ok=True, matched=False, match_count=0, notes=notes)

            trigger_items = self._load_trigger_items(rule)
            candidate_items = self._filter_new_items(rule, trigger_items)
            matching_items = self._matching_items(rule, candidate_items)
            match_count = len(matching_items)
            matched = match_count > 0

            notes.append(f"trigger_count={len(trigger_items)}")
            notes.append(f"candidate_count={len(candidate_items)}")

            if matched:
                executed_actions = 0
                for action in rule.actions:
                    if executed_actions >= rule.max_actions_per_run:
                        notes.append("action_cap_reached")
                        break
                    if isinstance(action, RuleActionNotify):
                        body = self._render_notify(
                            action.body_template,
                            count=match_count,
                            matching_items=matching_items,
                            now_iso=now.isoformat(),
                        )
                        self.notifier.send(title=action.title, body=body, meta={"rule_id": rule.id})
                        notes.append("notify_sent")
                        executed_actions += 1
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
                        executed_actions += 1

                state.last_match_iso = now.isoformat()
                if rule.cooldown_minutes > 0 and executed_actions > 0:
                    state.cooldown_until_iso = (now + timedelta(minutes=rule.cooldown_minutes)).isoformat()

            self._update_cursors(rule, candidate_items)
            self._sync_legacy_state(rule)

            self.memory_manager.episodic.append(
                kind="rule",
                summary=f"Ran rule {rule.name}: matched={matched} count={match_count}",
                meta={"rule_id": rule.id, "trigger_type": rule.trigger.type},
            )
            return RuleRunResult(rule_id=rule.id, ok=True, matched=matched, match_count=match_count, notes=notes)
        except Exception as exc:
            self._sync_legacy_state(rule)
            self.memory_manager.episodic.append(
                kind="rule",
                summary=f"Rule {rule.name} failed",
                meta={"rule_id": rule.id, "error": str(exc)},
            )
            return RuleRunResult(rule_id=rule.id, ok=False, matched=False, match_count=0, notes=notes, error=str(exc))

    def _is_cooldown_active(self, rule: Rule, now: datetime) -> bool:
        if rule.cooldown_minutes <= 0 or not rule.state.cooldown_until_iso:
            return False
        cooldown_until = self._parse_iso(rule.state.cooldown_until_iso)
        return cooldown_until is not None and cooldown_until > now

    def _load_trigger_items(self, rule: Rule) -> list[dict[str, Any]]:
        trigger = rule.trigger
        if trigger.type == "schedule":
            return [
                {
                    "item_id": f"schedule:{now_iso()}",
                    "ts_iso": None,
                    "text": "scheduler tick heartbeat",
                    "raw": {"title": "heartbeat", "snippet": "scheduler tick"},
                }
            ]

        if trigger.type == "gmail":
            if self.email_connector is None:
                return []
            messages = self.email_connector.search_messages(query=trigger.query or "", max_results=trigger.max_results)
            items: list[dict[str, Any]] = []
            for message in messages:
                item_id = str(message.get("thread_id") or message.get("id") or "")
                if not item_id:
                    continue
                text = " ".join(
                    [
                        str(message.get("from", "")),
                        str(message.get("subject", "")),
                        str(message.get("snippet", "")),
                    ]
                ).strip()
                items.append(
                    {
                        "item_id": item_id,
                        "ts_iso": message.get("date_iso"),
                        "text": text,
                        "raw": message,
                    }
                )
            return items

        if trigger.type == "calendar":
            if self.calendar_connector is None:
                return []
            now = datetime.now(timezone.utc)
            events = self.calendar_connector.search_events(
                calendar_id="primary",
                time_min_iso=now.isoformat(),
                time_max_iso=(now + timedelta(hours=trigger.hours_ahead)).isoformat(),
                query=trigger.query,
                max_results=trigger.max_results,
            )
            items: list[dict[str, Any]] = []
            for event in events:
                item_id = str(event.get("id") or "")
                if not item_id:
                    continue
                text = " ".join([str(event.get("title", "")), str(event.get("location", ""))]).strip()
                items.append(
                    {
                        "item_id": item_id,
                        "ts_iso": event.get("start_iso") or event.get("updated"),
                        "text": text,
                        "raw": event,
                    }
                )
            return items

        return []

    def _filter_new_items(self, rule: Rule, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen = set(rule.state.seen_ids)
        cursor = self._parse_iso(rule.state.last_cursor_iso)
        new_items: list[dict[str, Any]] = []
        for item in items:
            item_id = item["item_id"]
            if item_id in seen:
                continue
            item_ts = self._parse_iso(item.get("ts_iso"))
            if cursor and item_ts and item_ts <= cursor:
                continue
            new_items.append(item)
        return new_items

    def _matching_items(self, rule: Rule, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        contains = rule.condition.contains.casefold() if rule.condition.contains else None
        not_contains = rule.condition.not_contains.casefold() if rule.condition.not_contains else None

        if not contains and not not_contains:
            return list(items)

        matches: list[dict[str, Any]] = []
        for item in items:
            text = str(item.get("text", "")).casefold()
            if contains and contains not in text:
                continue
            if not_contains and not_contains in text:
                continue
            matches.append(item)
        return matches

    def _update_cursors(self, rule: Rule, processed_items: list[dict[str, Any]]) -> None:
        if not processed_items:
            return

        state = rule.state
        seen_ids = list(state.seen_ids)
        seen_set = set(seen_ids)
        max_dt = self._parse_iso(state.last_cursor_iso)
        max_iso = state.last_cursor_iso

        for item in processed_items:
            item_id = item["item_id"]
            if item_id in seen_set:
                seen_ids = [x for x in seen_ids if x != item_id]
            else:
                seen_set.add(item_id)
            seen_ids.append(item_id)

            item_ts_iso = item.get("ts_iso")
            item_ts = self._parse_iso(item_ts_iso)
            if item_ts and (max_dt is None or item_ts > max_dt):
                max_dt = item_ts
                max_iso = item_ts_iso

        seen_limit = max(1, state.seen_ids_max)
        state.seen_ids = seen_ids[-seen_limit:]
        state.last_cursor_iso = max_iso

    def _render_notify(self, template: str, count: int, matching_items: list[dict[str, Any]], now_iso: str) -> str:
        top_texts = [str(item.get("text", ""))[:280] for item in matching_items]
        rendered = template
        replacements = {
            "{{count}}": str(count),
            "{{top1}}": top_texts[0] if top_texts else "",
            "{{top2}}": top_texts[1] if len(top_texts) > 1 else "",
            "{{now_iso}}": now_iso,
        }
        for key, value in replacements.items():
            rendered = rendered.replace(key, value)
        return rendered

    def _sync_legacy_state(self, rule: Rule) -> None:
        rule.last_run_iso = rule.state.last_run_iso
        rule.last_match_iso = rule.state.last_match_iso

    @staticmethod
    def _parse_iso(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
