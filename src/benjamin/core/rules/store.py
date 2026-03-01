from __future__ import annotations

import json
from pathlib import Path

from .schemas import Rule, RuleState, now_iso


class RuleStore:
    def __init__(self, state_dir: Path) -> None:
        self.file_path = state_dir / "rules.jsonl"
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def _load_all(self) -> list[Rule]:
        if not self.file_path.exists():
            return []
        records: list[Rule] = []
        with self.file_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(self._migrate_rule(Rule.model_validate(json.loads(line))))
                except (json.JSONDecodeError, ValueError):
                    continue
        return records



    def _migrate_rule(self, rule: Rule) -> Rule:
        state = rule.state
        updates: dict[str, object] = {}
        if rule.last_run_iso and not state.last_run_iso:
            state = state.model_copy(update={"last_run_iso": rule.last_run_iso})
        if rule.last_match_iso and not state.last_match_iso:
            state = state.model_copy(update={"last_match_iso": rule.last_match_iso})
        if state.seen_ids_max <= 0:
            state = state.model_copy(update={"seen_ids_max": RuleState().seen_ids_max})
        if len(state.seen_ids) > state.seen_ids_max:
            state = state.model_copy(update={"seen_ids": state.seen_ids[-state.seen_ids_max :]})
        updates["state"] = state
        updates["last_run_iso"] = state.last_run_iso
        updates["last_match_iso"] = state.last_match_iso
        return rule.model_copy(update=updates)

    def _write_all(self, rules: list[Rule]) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        with self.file_path.open("w", encoding="utf-8") as handle:
            for rule in rules:
                normalized = self._migrate_rule(rule)
                handle.write(json.dumps(normalized.model_dump(), ensure_ascii=False) + "\n")

    def list_all(self) -> list[Rule]:
        return list(reversed(self._load_all()))

    def get(self, rule_id: str) -> Rule | None:
        for rule in self._load_all():
            if rule.id == rule_id:
                return rule
        return None

    def upsert(self, rule: Rule) -> Rule:
        rules = self._load_all()
        normalized = self._migrate_rule(rule)
        updated = normalized.model_copy(update={"updated_at_iso": now_iso()})
        for idx, current in enumerate(rules):
            if current.id == updated.id:
                rules[idx] = updated
                self._write_all(rules)
                return updated
        rules.append(updated)
        self._write_all(rules)
        return updated

    def delete(self, rule_id: str) -> bool:
        rules = self._load_all()
        filtered = [rule for rule in rules if rule.id != rule_id]
        if len(filtered) == len(rules):
            return False
        self._write_all(filtered)
        return True

    def set_enabled(self, rule_id: str, enabled: bool) -> Rule | None:
        rule = self.get(rule_id)
        if rule is None:
            return None
        return self.upsert(rule.model_copy(update={"enabled": enabled}))
