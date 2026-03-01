from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any


class PolicyOverridesStore:
    def __init__(self, state_dir: Path | None = None) -> None:
        self.state_dir = state_dir or self._state_dir_from_env()
        self.path = self.state_dir / "policy_overrides.json"

    def _state_dir_from_env(self) -> Path:
        configured = os.getenv("BENJAMIN_STATE_DIR")
        if configured:
            return Path(configured).expanduser()
        return Path.home() / ".benjamin"

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        if not isinstance(payload, dict):
            return {}
        return payload

    def save(self, overrides: dict[str, Any]) -> dict[str, Any]:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile("w", encoding="utf-8", dir=self.state_dir, suffix=".tmp", delete=False) as tmp:
            json.dump(overrides, tmp, ensure_ascii=False, indent=2, sort_keys=True)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp_path = Path(tmp.name)
        tmp_path.replace(self.path)
        return overrides
