from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from benjamin.core.ledger.schemas import LedgerRecord


class ExecutionLedger:
    def __init__(self, state_dir: str | Path) -> None:
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.state_dir / "executions.jsonl"
        self.lock_path = self.state_dir / "executions.lock"
        self.max_records = int(os.getenv("BENJAMIN_LEDGER_MAX", "5000"))
        self.lock_mode = os.getenv("BENJAMIN_LEDGER_LOCK_MODE", "file").casefold()

    def has_succeeded(self, key: str) -> bool:
        latest = self._latest_record_by_key().get(key)
        return latest is not None and latest.status == "succeeded"

    def try_start(
        self,
        key: str,
        kind: str,
        correlation_id: str | None = None,
        meta: dict | None = None,
    ) -> bool:
        with self._file_lock():
            latest = self._latest_record_by_key().get(key)
            if latest is not None and latest.status in {"succeeded", "started"}:
                return False

            self._append(
                LedgerRecord(
                    key=key,
                    kind=kind,
                    status="started",
                    ts_iso=self._now_iso(),
                    correlation_id=correlation_id,
                    meta=meta or {},
                )
            )
            self.trim(self.max_records)
            return True

    def mark(self, key: str, status: str, meta_update: dict | None = None) -> None:
        with self._file_lock():
            latest = self._latest_record_by_key().get(key)
            kind = latest.kind if latest is not None else "job_run"
            correlation_id = latest.correlation_id if latest is not None else None
            merged_meta: dict = dict(latest.meta) if latest is not None else {}
            if meta_update:
                merged_meta.update(meta_update)
            self._append(
                LedgerRecord(
                    key=key,
                    kind=kind,
                    status=status,
                    ts_iso=self._now_iso(),
                    correlation_id=correlation_id,
                    meta=merged_meta,
                )
            )
            self.trim(self.max_records)

    def list_recent(self, limit: int) -> list[LedgerRecord]:
        records = self._read_all_records()
        return records[-limit:] if limit > 0 else []

    def trim(self, max_records: int) -> None:
        if max_records <= 0:
            return
        records = self._read_all_records()
        if len(records) <= max_records:
            return
        keep = records[-max_records:]
        tmp_path = self.path.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as handle:
            for record in keep:
                handle.write(record.model_dump_json())
                handle.write("\n")
        tmp_path.replace(self.path)

    def _append(self, record: LedgerRecord) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(record.model_dump_json())
            handle.write("\n")

    def _read_all_records(self) -> list[LedgerRecord]:
        if not self.path.exists():
            return []
        records: list[LedgerRecord] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                raw = line.strip()
                if not raw:
                    continue
                try:
                    payload = json.loads(raw)
                    records.append(LedgerRecord.model_validate(payload))
                except Exception:
                    continue
        return records

    def _latest_record_by_key(self) -> dict[str, LedgerRecord]:
        latest: dict[str, LedgerRecord] = {}
        for record in self._read_all_records():
            latest[record.key] = record
        return latest

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    @contextmanager
    def _file_lock(self) -> Iterator[None]:
        if self.lock_mode != "file":
            yield
            return

        deadline = time.monotonic() + 2.0
        while True:
            try:
                fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.close(fd)
                break
            except FileExistsError:
                if time.monotonic() >= deadline:
                    break
                time.sleep(0.01)

        try:
            yield
        finally:
            if self.lock_path.exists():
                try:
                    self.lock_path.unlink()
                except FileNotFoundError:
                    pass
