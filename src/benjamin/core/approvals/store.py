from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from benjamin.core.approvals.schemas import PendingApproval


class ApprovalStore:
    def __init__(self, state_dir: Path | None = None) -> None:
        self.state_dir = state_dir or self._default_state_dir()
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.file_path = self.state_dir / "approvals.jsonl"

    def _default_state_dir(self) -> Path:
        configured = os.getenv("BENJAMIN_STATE_DIR")
        if configured:
            return Path(configured).expanduser()
        return Path.home() / ".benjamin"

    def _load_all(self) -> list[PendingApproval]:
        if not self.file_path.exists() or self.file_path.stat().st_size == 0:
            return []

        records: list[PendingApproval] = []
        with self.file_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(PendingApproval.model_validate(json.loads(line)))
                except (json.JSONDecodeError, ValueError):
                    continue
        return records

    def _rewrite(self, records: list[PendingApproval]) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        with self.file_path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record.model_dump(mode="json"), ensure_ascii=False) + "\n")

    def list_all(self, status: str | None = None) -> list[PendingApproval]:
        records = self._load_all()
        if status:
            records = [record for record in records if record.status == status]
        return sorted(records, key=lambda item: item.created_at_iso, reverse=True)

    def get(self, id: str) -> PendingApproval | None:
        for record in self._load_all():
            if record.id == id:
                return record
        return None

    def find_by_correlation(self, correlation_id: str, limit: int = 200) -> list[PendingApproval]:
        if limit <= 0:
            return []
        matches: list[PendingApproval] = []
        for record in self.list_all():
            requester_corr = str(record.requester.get("correlation_id", ""))
            context_corr = str(record.context.get("correlation_id", ""))
            if correlation_id in {requester_corr, context_corr}:
                matches.append(record)
            if len(matches) >= limit:
                break
        return matches

    def upsert(self, record: PendingApproval) -> None:
        records = self._load_all()
        updated = False
        for idx, current in enumerate(records):
            if current.id == record.id:
                records[idx] = record
                updated = True
                break
        if not updated:
            records.append(record)
        self._rewrite(records)

    def delete(self, id: str) -> None:
        records = [record for record in self._load_all() if record.id != id]
        self._rewrite(records)

    def cleanup_expired(self, now_iso: str) -> int:
        now = datetime.fromisoformat(now_iso)
        autoclean = os.getenv("BENJAMIN_APPROVALS_AUTOCLEAN", "on").casefold() != "off"
        changed = 0
        rewritten: list[PendingApproval] = []
        for record in self._load_all():
            if record.status == "pending" and datetime.fromisoformat(record.expires_at_iso) <= now:
                changed += 1
                if not autoclean:
                    record.status = "expired"
                    rewritten.append(record)
            else:
                rewritten.append(record)
        if changed:
            self._rewrite(rewritten)
        return changed


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
