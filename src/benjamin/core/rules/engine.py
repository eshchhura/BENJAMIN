from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from typing import Any

from benjamin.core.approvals.service import ApprovalService
from benjamin.core.ledger.keys import rule_action_key
from benjamin.core.ledger.ledger import ExecutionLedger
from benjamin.core.logging.context import log_context
from benjamin.core.memory.manager import MemoryManager
from benjamin.core.orchestration.schemas import ContextPack, PlanStep
from benjamin.core.security.policy import PermissionsPolicy
from benjamin.core.security.audit import log_policy_event
from benjamin.core.security.scopes import default_scopes_for_skill
from benjamin.core.skills.registry import SkillRegistry
from benjamin.core.infra.breaker_manager import ServiceDegradedError

from .schemas import (
    PlannedActionNotify,
    PlannedActionProposeStep,
    Rule,
    RuleActionNotify,
    RuleActionProposeStep,
    RuleMatchItem,
    RuleRunResult,
    RuleTestPreview,
    now_iso,
)


logger = logging.getLogger("benjamin.rules.engine")


class RuleEngine:
    def __init__(
        self,
        memory_manager: MemoryManager,
        approval_service: ApprovalService,
        registry: SkillRegistry,
        notifier,
        email_connector=None,
        calendar_connector=None,
        ledger: ExecutionLedger | None = None,
    ) -> None:
        self.memory_manager = memory_manager
        self.approval_service = approval_service
        self.registry = registry
        self.notifier = notifier
        self.email_connector = email_connector
        self.calendar_connector = calendar_connector
        self.ledger = ledger or ExecutionLedger(memory_manager.state_dir)
        self.permissions_policy = PermissionsPolicy()

    def evaluate_rule(self, rule: Rule, ctx: dict | None = None) -> RuleRunResult:
        correlation_id = str((ctx or {}).get("correlation_id") or uuid4())
        notes: list[str] = []
        with log_context(correlation_id=correlation_id, rule_id=rule.id):
            logger.info("rules_evaluation_started")
            return self._evaluate_rule(rule=rule, correlation_id=correlation_id, notes=notes)

    def _evaluate_rule(self, rule: Rule, correlation_id: str, notes: list[str]) -> RuleRunResult:
        state = rule.state
        now = datetime.now(timezone.utc)
        state.last_run_iso = now.isoformat()

        try:
            if self._is_cooldown_active(rule, now):
                notes.append("cooldown_active")
                self._sync_legacy_state(rule)
                return RuleRunResult(rule_id=rule.id, ok=True, matched=False, match_count=0, notes=notes)

            trigger_items, candidate_items, matching_items, match_notes = self.compute_matches(rule)
            match_count = len(matching_items)
            matched = match_count > 0

            notes.extend(match_notes)

            if matched:
                executed_actions = 0
                first_item_id = matching_items[0].get("item_id") if matching_items else None
                for action_index, action in enumerate(rule.actions):
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
                        self.notifier.send(title=action.title, body=body, meta={"rule_id": rule.id, "correlation_id": correlation_id})
                        notes.append("notify_sent")
                        executed_actions += 1
                    elif isinstance(action, RuleActionProposeStep):
                        action_signature = {
                            "skill_name": action.skill_name,
                            "args": action.args,
                            "rationale": action.rationale,
                        }
                        action_key = rule_action_key(
                            rule_id=rule.id,
                            action_index=action_index,
                            item_id=first_item_id,
                            signature=action_signature,
                        )
                        started = self.ledger.try_start(
                            action_key,
                            kind="rule_action",
                            correlation_id=correlation_id,
                            meta={"rule_id": rule.id, "item_id": first_item_id},
                        )
                        if not started:
                            notes.append("deduped_by_ledger")
                            continue

                        step = PlanStep(
                            description=f"Rule action for {action.skill_name}",
                            skill_name=action.skill_name,
                            args=json.dumps(action.args),
                            requires_approval=True,
                        )
                        required_scopes = self._required_scopes_for_skill(action.skill_name)
                        allowlist_ok, blocked_by_allowlist = self.permissions_policy.check_rules_allowlist(required_scopes)
                        snapshot = self.permissions_policy.snapshot_model()
                        if not allowlist_ok:
                            self.ledger.mark(action_key, "failed", meta_update={"error": "rules_scope_blocked", "blocked_scopes": blocked_by_allowlist})
                            notes.append("rules_scope_blocked")
                            log_policy_event(
                                self.memory_manager,
                                correlation_id=correlation_id,
                                source="rule",
                                decision="denied",
                                skill_name=action.skill_name,
                                required_scopes=required_scopes,
                                snapshot=snapshot,
                                reason="allowlist_blocked",
                                extra_meta={"rule_id": rule.id},
                            )
                            continue
                        scopes_ok, disabled_scopes = self.permissions_policy.check_scopes(required_scopes)
                        if not scopes_ok:
                            self.ledger.mark(action_key, "failed", meta_update={"error": "policy_denied", "disabled_scopes": disabled_scopes})
                            notes.append("policy_denied")
                            log_policy_event(
                                self.memory_manager,
                                correlation_id=correlation_id,
                                source="rule",
                                decision="denied",
                                skill_name=action.skill_name,
                                required_scopes=required_scopes,
                                snapshot=snapshot,
                                reason="scope_disabled",
                                extra_meta={"rule_id": rule.id},
                            )
                            continue
                        log_policy_event(
                            self.memory_manager,
                            correlation_id=correlation_id,
                            source="rule",
                            decision="allowed",
                            skill_name=action.skill_name,
                            required_scopes=required_scopes,
                            snapshot=snapshot,
                            reason="allowed",
                            extra_meta={"rule_id": rule.id},
                        )
                        try:
                            approval = self.approval_service.create_pending(
                                step=step,
                                ctx=ContextPack(goal=f"Rule matched: {rule.name}", cwd=None),
                                requester={"source": "rule", "rule_id": rule.id, "correlation_id": correlation_id},
                                rationale=action.rationale,
                                registry=self.registry,
                                required_scopes=required_scopes,
                            )
                            self.ledger.mark(action_key, "succeeded", meta_update={"approval_id": approval.id})
                            notes.append("approval_created")
                            executed_actions += 1
                        except Exception as exc:
                            self.ledger.mark(action_key, "failed", meta_update={"error": str(exc)})
                            raise

                state.last_match_iso = now.isoformat()
                if rule.cooldown_minutes > 0 and executed_actions > 0:
                    state.cooldown_until_iso = (now + timedelta(minutes=rule.cooldown_minutes)).isoformat()

            self._update_cursors(rule, candidate_items)
            self._sync_legacy_state(rule)

            self.memory_manager.episodic.append(
                kind="rule",
                summary=f"Ran rule {rule.name}: matched={matched} count={match_count}",
                meta={"rule_id": rule.id, "trigger_type": rule.trigger.type, "correlation_id": correlation_id},
            )
            logger.info("rules_evaluation_completed", extra={"extra_fields": {"matched": matched, "match_count": match_count}})
            return RuleRunResult(rule_id=rule.id, ok=True, matched=matched, match_count=match_count, notes=notes)
        except Exception as exc:
            self._sync_legacy_state(rule)
            self.memory_manager.episodic.append(
                kind="rule",
                summary=f"Rule {rule.name} failed",
                meta={"rule_id": rule.id, "error": str(exc), "correlation_id": correlation_id},
            )
            logger.exception("rules_evaluation_completed")
            return RuleRunResult(rule_id=rule.id, ok=False, matched=False, match_count=0, notes=notes, error=str(exc))

    def evaluate_rule_preview(self, rule: Rule, ctx: dict | None = None, include_seen: bool = False) -> RuleTestPreview:
        del ctx
        now = datetime.now(timezone.utc)
        trigger_items, candidate_items, matching_items, notes = self.compute_matches(rule, include_seen=include_seen)
        match_count = len(matching_items)

        if self._is_cooldown_active(rule, now):
            notes.append("blocked_by_cooldown")
            planned_actions: list[PlannedActionNotify | PlannedActionProposeStep] = []
        else:
            planned_actions = self.plan_actions(rule, matching_items, now_iso=now.isoformat(), notes=notes)

        return RuleTestPreview(
            rule_id=None if rule.id == "draft" else rule.id,
            rule_name=rule.name,
            matched=match_count > 0,
            match_count=match_count,
            candidate_count=len(candidate_items),
            matching_items=[
                RuleMatchItem(
                    item_id=str(item.get("item_id") or ""),
                    ts_iso=item.get("ts_iso"),
                    text=str(item.get("text") or ""),
                    raw=item.get("raw") or {},
                )
                for item in matching_items
            ],
            planned_actions=planned_actions,
            notes=notes,
        )

    def compute_matches(self, rule: Rule, include_seen: bool = False) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[str]]:
        notes: list[str] = []
        try:
            trigger_items = self._load_trigger_items(rule)
        except ServiceDegradedError as exc:
            service = exc.service
            notes.append(f"service_degraded:{service}")
            return [], [], [], notes

        candidate_items = trigger_items if include_seen else self._filter_new_items(rule, trigger_items)
        matching_items = self._matching_items(rule, candidate_items)
        notes.extend([f"trigger_count={len(trigger_items)}", f"candidate_count={len(candidate_items)}"])
        if include_seen:
            notes.append("include_seen=true")
        return trigger_items, candidate_items, matching_items, notes

    def plan_actions(
        self,
        rule: Rule,
        matching_items: list[dict[str, Any]],
        now_iso: str,
        notes: list[str] | None = None,
    ) -> list[PlannedActionNotify | PlannedActionProposeStep]:
        applied_notes = notes if notes is not None else []
        planned_actions: list[PlannedActionNotify | PlannedActionProposeStep] = []
        if not matching_items:
            return planned_actions

        for action in rule.actions:
            if len(planned_actions) >= rule.max_actions_per_run:
                applied_notes.append("action_cap_reached")
                break
            if isinstance(action, RuleActionNotify):
                planned_actions.append(
                    PlannedActionNotify(
                        type="notify",
                        title=action.title,
                        body=self._render_notify(
                            action.body_template,
                            count=len(matching_items),
                            matching_items=matching_items,
                            now_iso=now_iso,
                        ),
                    )
                )
            elif isinstance(action, RuleActionProposeStep):
                required_scopes = self._required_scopes_for_skill(action.skill_name)
                blocked_reason = None
                allowlist_ok, blocked_by_allowlist = self.permissions_policy.check_rules_allowlist(required_scopes)
                if not allowlist_ok:
                    blocked_reason = f"rule allowlist blocks: {', '.join(blocked_by_allowlist)}"
                else:
                    scopes_ok, disabled_scopes = self.permissions_policy.check_scopes(required_scopes)
                    if not scopes_ok:
                        blocked_reason = f"scope disabled: {', '.join(disabled_scopes)}"
                planned_actions.append(
                    PlannedActionProposeStep(
                        type="propose_step",
                        skill_name=action.skill_name,
                        args=action.args,
                        rationale=action.rationale,
                        would_create_approval=blocked_reason is None,
                        required_scopes=required_scopes,
                        blocked=blocked_reason is not None,
                        blocked_reason=blocked_reason,
                    )
                )
        return planned_actions

    def _required_scopes_for_skill(self, skill_name: str) -> list[str]:
        try:
            skill = self.registry.get(skill_name)
            scopes = list(getattr(skill, "required_scopes", []) or [])
            if scopes:
                return scopes
            return default_scopes_for_skill(skill_name, getattr(skill, "side_effect", "read"))
        except KeyError:
            return default_scopes_for_skill(skill_name, "write")

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
