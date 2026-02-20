from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .schemas import Episode


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class EpisodicMemoryStore:
    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def _load_all(self) -> list[Episode]:
        if not self.file_path.exists():
            return []

        episodes: list[Episode] = []
        with self.file_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    episodes.append(Episode.model_validate(json.loads(line)))
                except (json.JSONDecodeError, ValueError):
                    continue
        return episodes

    def append(self, kind: str, summary: str, meta: dict[str, Any] | None = None) -> Episode:
        episode = Episode(id=str(uuid4()), kind=kind, summary=summary, ts_iso=_now_iso(), meta=meta or {})
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        with self.file_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(episode.model_dump(), ensure_ascii=False) + "\n")
        return episode

    def list_recent(self, limit: int) -> list[Episode]:
        episodes = self._load_all()
        if limit <= 0:
            return []
        return episodes[-limit:]

    def search(self, text: str, limit: int) -> list[Episode]:
        query = text.casefold().strip()
        episodes = self._load_all()
        if not query:
            return episodes[-limit:]

        matches: list[Episode] = []
        for episode in reversed(episodes):
            haystack = " ".join([episode.kind, episode.summary, json.dumps(episode.meta, ensure_ascii=False)]).casefold()
            if query in haystack:
                matches.append(episode)
            if len(matches) >= limit:
                break
        return list(reversed(matches))
