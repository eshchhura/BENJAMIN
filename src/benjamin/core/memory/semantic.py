from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .schemas import SemanticFact


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SemanticMemoryStore:
    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def _load_all(self) -> list[SemanticFact]:
        if not self.file_path.exists():
            return []

        items: list[SemanticFact] = []
        with self.file_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    items.append(SemanticFact.model_validate(json.loads(line)))
                except (json.JSONDecodeError, ValueError):
                    continue
        return items

    def _write_all(self, facts: list[SemanticFact]) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        with self.file_path.open("w", encoding="utf-8") as handle:
            for fact in facts:
                handle.write(json.dumps(fact.model_dump(), ensure_ascii=False) + "\n")

    def upsert(self, key: str, value: str, scope: str = "global", tags: list[str] | None = None) -> SemanticFact:
        tags = tags or []
        now = _now_iso()
        facts = self._load_all()

        for index, fact in enumerate(facts):
            if fact.scope == scope and fact.key == key:
                updated = fact.model_copy(
                    update={
                        "value": value,
                        "tags": tags,
                        "updated_at_iso": now,
                    }
                )
                facts[index] = updated
                self._write_all(facts)
                return updated

        new_fact = SemanticFact(
            id=str(uuid4()),
            key=key,
            value=value,
            scope=scope,
            tags=tags,
            created_at_iso=now,
            updated_at_iso=now,
        )
        facts.append(new_fact)
        self._write_all(facts)
        return new_fact

    def list_all(self, scope: str | None = None) -> list[SemanticFact]:
        facts = self._load_all()
        if scope is None:
            return facts
        return [fact for fact in facts if fact.scope == scope]

    def search(self, text: str, limit: int) -> list[SemanticFact]:
        query = text.casefold().strip()
        if not query:
            return self.list_all()[:limit]

        matches: list[SemanticFact] = []
        for fact in self._load_all():
            haystack = " ".join([fact.key, fact.value, " ".join(fact.tags)]).casefold()
            if query in haystack:
                matches.append(fact)
            if len(matches) >= limit:
                break
        return matches
