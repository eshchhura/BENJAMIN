from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile


def _state_dir_path(state_dir: str | Path) -> Path:
    return Path(state_dir).expanduser()


def _safe_mode_file(state_dir: str | Path) -> Path:
    root = _state_dir_path(state_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root / "safe_mode.json"


def _env_forced_on() -> bool:
    return os.getenv("BENJAMIN_SAFE_MODE", "off").strip().casefold() == "on"


def is_safe_mode_enabled(state_dir: str | Path) -> bool:
    if _env_forced_on():
        return True
    path = _safe_mode_file(state_dir)
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    return bool(payload.get("enabled", False))


def set_safe_mode_enabled(state_dir: str | Path, enabled: bool) -> None:
    path = _safe_mode_file(state_dir)
    payload = {"enabled": bool(enabled)}
    with NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent) as handle:
        json.dump(payload, handle)
        handle.flush()
        os.fsync(handle.fileno())
        temp_name = handle.name
    Path(temp_name).replace(path)


def safe_mode_env_forced() -> bool:
    return _env_forced_on()


def safe_mode_allow_summarizer() -> bool:
    return os.getenv("BENJAMIN_SAFE_MODE_ALLOW_SUMMARIZER", "on").strip().casefold() == "on"


def safe_mode_allow_rule_builder() -> bool:
    return os.getenv("BENJAMIN_SAFE_MODE_ALLOW_RULE_BUILDER", "off").strip().casefold() == "on"
