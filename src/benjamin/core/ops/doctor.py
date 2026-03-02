from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Callable, Literal

from pydantic import BaseModel, Field, RootModel, ValidationError

from benjamin.core.approvals.schemas import PendingApproval
from benjamin.core.ledger.schemas import LedgerRecord
from benjamin.core.memory.schemas import Episode, SemanticFact
from benjamin.core.rules.schemas import Rule
from benjamin.core.runs.schemas import TaskRecord


class DoctorFileReport(BaseModel):
    name: str
    path: str
    exists: bool
    size_bytes: int
    format: Literal["json", "jsonl"]
    record_count: int | None = None
    valid_count: int | None = None
    invalid_count: int | None = None
    last_ts_iso: str | None = None
    notes: list[str] = Field(default_factory=list)


class DoctorSummary(BaseModel):
    total_files: int
    missing: int
    invalid_lines: int
    total_bytes: int


class DoctorReport(BaseModel):
    ok: bool
    state_dir: str
    ts_iso: str
    files: list[DoctorFileReport]
    summary: DoctorSummary


class PolicyOverridesSnapshot(BaseModel):
    scopes_enabled: list[str] = Field(default_factory=list)
    rules_allowed_scopes: list[str] = Field(default_factory=list)


class BreakerItemSnapshot(BaseModel):
    state: str | None = None
    failure_count: int | None = None
    opened_at_iso: str | None = None
    updated_at_iso: str | None = None


class BreakerSnapshot(RootModel[dict[str, BreakerItemSnapshot]]):
    pass


@dataclass(frozen=True)
class KnownArtifact:
    name: str
    format: Literal["json", "jsonl"]
    model: type[BaseModel] | None = None
    timestamp_getter: Callable[[Any], str | None] | None = None
    retention_env: str | None = None
    retention_default: int | None = None
    critical: bool = True


def _state_dir_from_env(state_dir: str | Path | None = None) -> Path:
    if state_dir is not None:
        return Path(state_dir).expanduser()
    configured = os.getenv("BENJAMIN_STATE_DIR")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".benjamin"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _timestamp_or_none(value: str | None) -> datetime | None:
    if not value:
        return None
    candidate = value.strip()
    if not candidate:
        return None
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(candidate)
    except ValueError:
        return None


def _max_ts(current: str | None, candidate: str | None) -> str | None:
    c1 = _timestamp_or_none(current)
    c2 = _timestamp_or_none(candidate)
    if c2 is None:
        return current
    if c1 is None or c2 > c1:
        return candidate
    return current


def _jsonl_report(path: Path, artifact: KnownArtifact) -> tuple[DoctorFileReport, list[dict[str, Any]]]:
    report = DoctorFileReport(
        name=artifact.name,
        path=str(path),
        exists=path.exists(),
        size_bytes=path.stat().st_size if path.exists() else 0,
        format="jsonl",
        record_count=0,
        valid_count=0,
        invalid_count=0,
        last_ts_iso=None,
        notes=[],
    )
    valid_payloads: list[dict[str, Any]] = []
    if not path.exists():
        report.notes.append("file missing")
        return report, valid_payloads

    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            raw = line.strip()
            if not raw:
                continue
            report.record_count = (report.record_count or 0) + 1
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as exc:
                report.invalid_count = (report.invalid_count or 0) + 1
                if len(report.notes) < 3:
                    report.notes.append(f"line {line_no}: JSONDecodeError {exc.msg}")
                continue

            validated: Any = payload
            if artifact.model is not None:
                try:
                    validated = artifact.model.model_validate(payload)
                except ValidationError as exc:
                    report.invalid_count = (report.invalid_count or 0) + 1
                    if len(report.notes) < 3:
                        report.notes.append(f"line {line_no}: ValidationError {exc.errors()[0].get('loc')}")
                    continue

            report.valid_count = (report.valid_count or 0) + 1
            if artifact.timestamp_getter is not None:
                report.last_ts_iso = _max_ts(report.last_ts_iso, artifact.timestamp_getter(validated))
            valid_payloads.append(validated.model_dump() if isinstance(validated, BaseModel) else payload)

    return report, valid_payloads


def _json_report(path: Path, artifact: KnownArtifact) -> DoctorFileReport:
    report = DoctorFileReport(
        name=artifact.name,
        path=str(path),
        exists=path.exists(),
        size_bytes=path.stat().st_size if path.exists() else 0,
        format="json",
        notes=[],
    )
    if not path.exists():
        report.notes.append("file missing")
        return report

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        report.notes.append(f"invalid JSON: {exc.msg}")
        report.invalid_count = 1
        return report
    except OSError as exc:
        report.notes.append(f"failed to read file: {exc}")
        report.invalid_count = 1
        return report

    if artifact.model is not None:
        try:
            artifact.model.model_validate(payload)
        except ValidationError as exc:
            report.invalid_count = 1
            report.notes.append(f"ValidationError: {exc.errors()[0].get('loc')}")
            return report

    report.valid_count = 1
    return report


def _write_jsonl_atomic(path: Path, rows: list[dict[str, Any]]) -> None:
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, suffix=".tmp", delete=False) as tmp:
        for row in rows:
            tmp.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
            tmp.write("\n")
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def _backup_path(path: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return path.with_name(f"{path.name}.bak.{stamp}")


def _apply_backup_and_replace(path: Path, rows: list[dict[str, Any]]) -> None:
    backup = _backup_path(path)
    shutil.copy2(path, backup)
    _write_jsonl_atomic(path, rows)


def _retention_max(artifact: KnownArtifact) -> int | None:
    if artifact.retention_env is None:
        return None
    raw = os.getenv(artifact.retention_env, str(artifact.retention_default or ""))
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return artifact.retention_default
    return value if value > 0 else None


def _compact_rows(artifact: KnownArtifact, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    retention = _retention_max(artifact)
    compacted = list(rows)
    if artifact.name in {"episodic", "tasks"}:
        seen: set[str] = set()
        deduped: list[dict[str, Any]] = []
        for row in reversed(compacted):
            row_id = str(row.get("id") or row.get("task_id") or "")
            if row_id and row_id in seen:
                continue
            if row_id:
                seen.add(row_id)
            deduped.append(row)
        compacted = list(reversed(deduped))
    if retention is not None and len(compacted) > retention:
        compacted = compacted[-retention:]
    return compacted


def _known_artifacts() -> list[KnownArtifact]:
    return [
        KnownArtifact("semantic", "jsonl", model=SemanticFact, timestamp_getter=lambda item: item.updated_at_iso),
        KnownArtifact(
            "episodic",
            "jsonl",
            model=Episode,
            timestamp_getter=lambda item: item.ts_iso,
            retention_env="BENJAMIN_EPISODES_MAX",
            retention_default=5000,
        ),
        KnownArtifact("approvals", "jsonl", model=PendingApproval, timestamp_getter=lambda item: item.created_at_iso),
        KnownArtifact("rules", "jsonl", model=Rule, timestamp_getter=lambda item: item.updated_at_iso),
        KnownArtifact(
            "tasks",
            "jsonl",
            model=TaskRecord,
            timestamp_getter=lambda item: item.ts_iso,
            retention_env="BENJAMIN_TASKS_MAX",
            retention_default=500,
        ),
        KnownArtifact(
            "executions",
            "jsonl",
            model=LedgerRecord,
            timestamp_getter=lambda item: item.ts_iso,
            retention_env="BENJAMIN_LEDGER_MAX",
            retention_default=5000,
        ),
        KnownArtifact("breakers", "json", model=BreakerSnapshot, critical=False),
        KnownArtifact("policy_overrides", "json", model=PolicyOverridesSnapshot, critical=False),
    ]


def _artifact_path(state_dir: Path, artifact: KnownArtifact) -> Path:
    ext = "json" if artifact.format == "json" else "jsonl"
    return state_dir / f"{artifact.name}.{ext}"


def run_doctor(state_dir: str | Path | None = None, repair: bool = False, compact: bool = False) -> DoctorReport:
    root = _state_dir_from_env(state_dir)
    root.mkdir(parents=True, exist_ok=True)

    file_reports: list[DoctorFileReport] = []
    total_invalid = 0
    total_missing = 0
    total_bytes = 0

    for artifact in _known_artifacts():
        path = _artifact_path(root, artifact)
        if artifact.format == "jsonl":
            report, valid_rows = _jsonl_report(path, artifact)
            initial_invalid = report.invalid_count or 0
            changed = False
            if repair and initial_invalid > 0 and path.exists():
                _apply_backup_and_replace(path, valid_rows)
                changed = True
            if compact and path.exists():
                compacted = _compact_rows(artifact, valid_rows)
                if compacted != valid_rows:
                    _apply_backup_and_replace(path, compacted)
                    changed = True
            if changed:
                report, _ = _jsonl_report(path, artifact)
                report.notes.append("file rewritten by doctor")
        else:
            report = _json_report(path, artifact)

        total_invalid += report.invalid_count or 0
        total_missing += 0 if report.exists else 1
        total_bytes += report.size_bytes
        file_reports.append(report)

    critical_invalid = 0
    for artifact, report in zip(_known_artifacts(), file_reports):
        if artifact.critical:
            critical_invalid += report.invalid_count or 0

    ok = critical_invalid == 0

    return DoctorReport(
        ok=ok,
        state_dir=str(root),
        ts_iso=_now_iso(),
        files=file_reports,
        summary=DoctorSummary(
            total_files=len(file_reports),
            missing=total_missing,
            invalid_lines=total_invalid,
            total_bytes=total_bytes,
        ),
    )
