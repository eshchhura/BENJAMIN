from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any
from uuid import uuid4

from benjamin.core.memory.manager import MemoryManager
from benjamin.core.notifications.notifier import NotificationRouter
from benjamin.core.ops.doctor import DoctorReport, run_doctor
from benjamin.core.ops.safe_mode import is_safe_mode_enabled

MAINTENANCE_STATUS_FILE = "maintenance.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _state_dir_path(state_dir: str | Path) -> Path:
    return Path(state_dir).expanduser()


def _default_job_status() -> dict[str, Any]:
    return {
        "last_run_iso": None,
        "ok": None,
        "summary": {},
        "details": {},
        "correlation_id": None,
    }


def default_maintenance_status() -> dict[str, dict[str, Any]]:
    return {
        "doctor_validate": _default_job_status(),
        "weekly_compact": _default_job_status(),
    }


def load_maintenance_status(state_dir: str | Path) -> dict[str, dict[str, Any]]:
    root = _state_dir_path(state_dir)
    path = root / MAINTENANCE_STATUS_FILE
    status = default_maintenance_status()
    if not path.exists():
        return status
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return status
    if not isinstance(loaded, dict):
        return status
    for key in status:
        value = loaded.get(key)
        if isinstance(value, dict):
            status[key] = {**status[key], **value}
    return status


def save_maintenance_status(state_dir: str | Path, status: dict[str, dict[str, Any]]) -> None:
    root = _state_dir_path(state_dir)
    root.mkdir(parents=True, exist_ok=True)
    path = root / MAINTENANCE_STATUS_FILE
    with NamedTemporaryFile("w", encoding="utf-8", dir=root, suffix=".tmp", delete=False) as tmp:
        json.dump(status, tmp, ensure_ascii=False, indent=2)
        tmp.write("\n")
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def _notify_enabled_on_ok() -> bool:
    return os.getenv("BENJAMIN_MAINTENANCE_NOTIFY_ON_OK", "off").strip().casefold() == "on"


def _write_episode(memory_manager: MemoryManager, job: str, ok: bool, summary: dict[str, Any], correlation_id: str) -> None:
    memory_manager.episodic.append(
        kind="maintenance",
        summary=f"Maintenance {job} {'ok' if ok else 'issue'}",
        meta={"job": job, "ok": ok, "summary": summary, "correlation_id": correlation_id},
    )


def _update_job_status(
    state_dir: str | Path,
    job_name: str,
    ok: bool,
    summary: dict[str, Any],
    details: dict[str, Any],
    correlation_id: str,
) -> dict[str, dict[str, Any]]:
    status = load_maintenance_status(state_dir)
    status[job_name] = {
        "last_run_iso": _now_iso(),
        "ok": ok,
        "summary": summary,
        "details": details,
        "correlation_id": correlation_id,
    }
    save_maintenance_status(state_dir, status)
    return status


def run_doctor_validate(
    state_dir: str | Path,
    notifier: NotificationRouter,
    memory_manager: MemoryManager,
    breaker_manager: Any = None,
    safe_mode_snapshot: bool | None = None,
) -> DoctorReport:
    correlation_id = str(uuid4())
    report = run_doctor(state_dir=state_dir, repair=False, compact=False)
    critical_invalid = 0
    for file_report in report.files:
        if file_report.name in {"tasks", "episodic", "executions", "rules", "approvals", "semantic"}:
            critical_invalid += file_report.invalid_count or 0

    summary = {
        "invalid_lines": report.summary.invalid_lines,
        "missing": report.summary.missing,
        "critical_invalid_lines": critical_invalid,
        "total_files": report.summary.total_files,
    }
    details = {
        "report": report.model_dump(),
        "safe_mode_enabled": safe_mode_snapshot if safe_mode_snapshot is not None else is_safe_mode_enabled(_state_dir_path(state_dir)),
        "breakers": breaker_manager.snapshot() if breaker_manager is not None else {},
    }
    ok = bool(report.ok and critical_invalid == 0)
    _update_job_status(state_dir, "doctor_validate", ok, summary, details, correlation_id)
    _write_episode(memory_manager, "doctor_validate", ok, summary, correlation_id)

    if (not ok) or _notify_enabled_on_ok():
        severity = "ok" if ok else "critical"
        notifier.send(
            title=f"Maintenance: Doctor Validate ({severity})",
            body=(
                f"job=doctor_validate status={severity} invalid_lines={summary['invalid_lines']} "
                f"critical_invalid_lines={summary['critical_invalid_lines']} missing={summary['missing']} "
                "See /ui/doctor and /ui/ops"
            ),
            meta={"correlation_id": correlation_id, "job": "doctor_validate", "ok": ok},
        )
    return report


def run_weekly_compact(state_dir: str | Path, notifier: NotificationRouter, memory_manager: MemoryManager) -> dict[str, Any]:
    correlation_id = str(uuid4())
    root = _state_dir_path(state_dir)

    def _line_count(path: Path) -> int:
        if not path.exists():
            return 0
        with path.open("r", encoding="utf-8") as handle:
            return sum(1 for line in handle if line.strip())

    tracked = ["tasks", "episodic", "executions"]
    before: dict[str, dict[str, int]] = {}
    for name in tracked:
        path = root / f"{name}.jsonl"
        before[name] = {"lines": _line_count(path), "bytes": path.stat().st_size if path.exists() else 0}

    run_doctor(state_dir=root, compact=True)

    trimmed_total = 0
    bytes_saved_total = 0
    per_file: dict[str, Any] = {}
    for name in tracked:
        path = root / f"{name}.jsonl"
        after_lines = _line_count(path)
        after_bytes = path.stat().st_size if path.exists() else 0
        trimmed = max(0, before[name]["lines"] - after_lines)
        saved = max(0, before[name]["bytes"] - after_bytes)
        trimmed_total += trimmed
        bytes_saved_total += saved
        per_file[name] = {
            "lines_before": before[name]["lines"],
            "lines_after": after_lines,
            "trimmed": trimmed,
            "bytes_before": before[name]["bytes"],
            "bytes_after": after_bytes,
            "bytes_saved": saved,
        }

    summary = {
        "trimmed_total": trimmed_total,
        "bytes_saved_total": bytes_saved_total,
        "files": per_file,
    }
    ok = True
    _update_job_status(state_dir, "weekly_compact", ok, summary, {"files": per_file}, correlation_id)
    _write_episode(memory_manager, "weekly_compact", ok, summary, correlation_id)

    if trimmed_total > 0 or bytes_saved_total > 0 or _notify_enabled_on_ok():
        notifier.send(
            title="Maintenance: Weekly Compact",
            body=(
                f"job=weekly_compact status=ok trimmed={trimmed_total} bytes_saved={bytes_saved_total} "
                "See /ui/ops"
            ),
            meta={"correlation_id": correlation_id, "job": "weekly_compact", "ok": True},
        )

    return {"ok": True, "summary": summary, "correlation_id": correlation_id}
