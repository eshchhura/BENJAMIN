from __future__ import annotations

import re

_SECRET_KEY_RE = re.compile(r"(TOKEN|KEY|SECRET|WEBHOOK)", re.IGNORECASE)
_SECRET_VALUE_RE = re.compile(r"(?i)(token|key|secret|webhook)(\s*[=:]\s*)([^\s,;]+)")
_BEARER_RE = re.compile(r"(?i)(bearer\s+)([^\s]+)")


def redact_string(s: str) -> str:
    redacted = _SECRET_VALUE_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}***", s)
    redacted = _BEARER_RE.sub(lambda m: f"{m.group(1)}***", redacted)
    return redacted


def redact_env(env: dict) -> dict:
    output = dict(env)
    for key in list(output.keys()):
        if _SECRET_KEY_RE.search(str(key)):
            output[key] = "***"
    return output
