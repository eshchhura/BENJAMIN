#!/usr/bin/env python3
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from urllib import error, request


REQUIRED_PYTHON = (3, 11)


def _is_on(name: str, default: str = "off") -> bool:
    return os.getenv(name, default).strip().casefold() == "on"


def _state_dir() -> Path:
    configured = os.getenv("BENJAMIN_STATE_DIR")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".benjamin"


def _google_token_path(state_dir: Path) -> Path:
    configured = os.getenv("BENJAMIN_GOOGLE_TOKEN_PATH")
    if configured:
        return Path(configured).expanduser()
    return state_dir / "google_token.json"


def _base_vllm_url() -> str:
    raw = os.getenv("BENJAMIN_VLLM_URL", "http://127.0.0.1:8001/v1/chat/completions").strip()
    if raw.endswith("/v1/chat/completions"):
        return raw[: -len("/v1/chat/completions")]
    return raw.rstrip("/")


def _check_vllm(url: str) -> tuple[bool, str]:
    models_url = f"{url}/v1/models"
    req = request.Request(models_url, method="GET")
    try:
        with request.urlopen(req, timeout=1.0) as resp:  # nosec B310
            if 200 <= resp.status < 500:
                return True, f"reachable via GET {models_url}"
    except Exception:
        pass

    chat_url = f"{url}/v1/chat/completions"
    payload = (
        b'{"model":"test","messages":[{"role":"user","content":"ping"}],"max_tokens":1}'
    )
    req = request.Request(chat_url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with request.urlopen(req, timeout=1.0) as resp:  # nosec B310
            if 200 <= resp.status < 500:
                return True, f"reachable via POST {chat_url}"
    except error.URLError as exc:
        return False, f"{exc}"
    except Exception as exc:  # pragma: no cover - defensive
        return False, f"{exc}"
    return False, "unknown error"


def main() -> int:
    errors: list[str] = []

    if sys.version_info >= REQUIRED_PYTHON:
        print(f"OK: Python {sys.version.split()[0]} (>= 3.11)")
    else:
        errors.append(
            "Python 3.11+ is required. Fix: install Python 3.11+ and recreate your virtual environment."
        )

    try:
        importlib.import_module("benjamin")
        print("OK: import benjamin")
    except Exception as exc:
        errors.append(
            f"Could not import benjamin ({exc}). Fix: run `python -m pip install -e .[dev]` from repo root."
        )

    state_dir = _state_dir()
    try:
        state_dir.mkdir(parents=True, exist_ok=True)
        probe = state_dir / ".write-check"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        print(f"OK: BENJAMIN_STATE_DIR writable at {state_dir}")
    except Exception as exc:
        errors.append(
            f"BENJAMIN_STATE_DIR is not writable ({state_dir}): {exc}. "
            "Fix: set BENJAMIN_STATE_DIR to a writable directory."
        )

    auth_mode = os.getenv("BENJAMIN_AUTH_MODE", "token").strip().casefold()
    auth_enabled = auth_mode != "off"
    if auth_enabled:
        if os.getenv("BENJAMIN_AUTH_TOKEN"):
            print("OK: auth enabled and BENJAMIN_AUTH_TOKEN is set")
        else:
            errors.append(
                "Auth is enabled but BENJAMIN_AUTH_TOKEN is missing. "
                "Fix: export BENJAMIN_AUTH_TOKEN=<your-token> or set BENJAMIN_AUTH_MODE=off for local dev."
            )
    else:
        print("OK: auth disabled (BENJAMIN_AUTH_MODE=off)")

    google_enabled = _is_on("BENJAMIN_GOOGLE_ENABLED", default="off")
    if google_enabled:
        token_path = _google_token_path(state_dir)
        if token_path.exists():
            print(f"OK: Google token file found at {token_path}")
        else:
            errors.append(
                f"Google integrations are enabled but token file is missing at {token_path}. "
                "Fix: provide BENJAMIN_GOOGLE_TOKEN_PATH or disable with BENJAMIN_GOOGLE_ENABLED=off."
            )
    else:
        print("OK: Google integrations disabled")

    provider = os.getenv("BENJAMIN_LLM_PROVIDER", "off").strip().casefold()
    if provider == "vllm":
        llm_url = _base_vllm_url()
        reachable, detail = _check_vllm(llm_url)
        if reachable:
            print(f"OK: vLLM endpoint {llm_url} is reachable ({detail})")
        else:
            errors.append(
                f"vLLM provider enabled but endpoint is unreachable ({llm_url}): {detail}. "
                "Fix: start vLLM, verify BENJAMIN_VLLM_URL, and ensure the port is accessible."
            )
    else:
        print(f"OK: LLM provider is {provider}")

    expect_worker = os.getenv("BENJAMIN_DEV_EXPECT_WORKER", "on").strip().casefold() not in {"off", "0", "false", "no"}
    if expect_worker:
        try:
            from benjamin.core.scheduler.scheduler import SchedulerService

            scheduler = SchedulerService(state_dir=state_dir)
            _ = scheduler.timezone
            _ = scheduler.scheduler
            print("OK: scheduler service can be constructed for worker")
        except Exception as exc:
            errors.append(
                f"Worker scheduler failed to initialize: {exc}. "
                "Fix: verify scheduler dependencies and BENJAMIN_STATE_DIR permissions."
            )
    else:
        print("OK: worker checks skipped (BENJAMIN_DEV_EXPECT_WORKER=off)")

    if errors:
        for message in errors:
            print(f"ERROR: {message}")
        return 1

    print("OK: environment check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
