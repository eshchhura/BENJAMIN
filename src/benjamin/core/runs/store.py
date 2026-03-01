from __future__ import annotations

import json
from pathlib import Path

from .schemas import TaskRecord


class TaskStore:
    def __init__(self, state_dir: Path, max_records: int = 500) -> None:
        self.file_path = state_dir / "tasks.jsonl"
        self.max_records = max(1, max_records)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def _load_all(self) -> list[TaskRecord]:
        if not self.file_path.exists():
            return []
        records: list[TaskRecord] = []
        with self.file_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(TaskRecord.model_validate(json.loads(line)))
                except (json.JSONDecodeError, ValueError):
                    continue
        return records

    def _write_all(self, records: list[TaskRecord]) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        with self.file_path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record.model_dump(), ensure_ascii=False) + "\n")

    def append(self, record: TaskRecord) -> TaskRecord:
        with self.file_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record.model_dump(), ensure_ascii=False) + "\n")
        self.trim(self.max_records)
        return record

    def list_recent(self, limit: int = 50) -> list[TaskRecord]:
        if limit <= 0:
            return []
        records = self._load_all()
        return list(reversed(records[-limit:]))

    def search(self, q: str, limit: int = 50) -> list[TaskRecord]:
        query = q.casefold().strip()
        if limit <= 0:
            return []

        records = self._load_all()
        if not query:
            return list(reversed(records[-limit:]))

        matches: list[TaskRecord] = []
        for record in reversed(records):
            haystack = " ".join(
                [
                    record.task_id,
                    record.correlation_id,
                    record.user_message,
                    record.answer,
                ]
            ).casefold()
            if query in haystack:
                matches.append(record)
            if len(matches) >= limit:
                break
        return matches

    def get(self, task_id: str) -> TaskRecord | None:
        for record in reversed(self._load_all()):
            if record.task_id == task_id:
                return record
        return None

    def trim(self, max_records: int) -> None:
        max_records = max(1, max_records)
        records = self._load_all()
        if len(records) <= max_records:
            return
        self._write_all(records[-max_records:])
