from __future__ import annotations

import json
from pathlib import Path

from .schemas import Rule, now_iso


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
                    records.append(Rule.model_validate(json.loads(line)))
                except (json.JSONDecodeError, ValueError):
                    continue
        return records

    def _write_all(self, rules: list[Rule]) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        with self.file_path.open("w", encoding="utf-8") as handle:
            for rule in rules:
                handle.write(json.dumps(rule.model_dump(), ensure_ascii=False) + "\n")

    def list_all(self) -> list[Rule]:
        return list(reversed(self._load_all()))

    def get(self, rule_id: str) -> Rule | None:
        for rule in self._load_all():
            if rule.id == rule_id:
                return rule
        return None

    def upsert(self, rule: Rule) -> Rule:
        rules = self._load_all()
        updated = rule.model_copy(update={"updated_at_iso": now_iso()})
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
