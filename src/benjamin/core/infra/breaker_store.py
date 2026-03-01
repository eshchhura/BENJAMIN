from __future__ import annotations

import json
from pathlib import Path


class BreakerStore:
    def __init__(self, state_dir: Path) -> None:
        self.state_dir = state_dir
        self.path = self.state_dir / "breakers.json"

    def load(self) -> dict[str, dict[str, object]]:
        if not self.path.exists():
            return {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        if not isinstance(raw, dict):
            return {}
        result: dict[str, dict[str, object]] = {}
        for key, value in raw.items():
            if isinstance(key, str) and isinstance(value, dict):
                result[key] = value
        return result

    def save(self, payload: dict[str, dict[str, object]]) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(self.path)
