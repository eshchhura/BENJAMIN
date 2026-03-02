from __future__ import annotations

import json

from benjamin.core.ops.doctor import run_doctor


def test_doctor_repairs_corrupt_jsonl(tmp_path):
    episodic = tmp_path / "episodic.jsonl"
    valid1 = {"id": "e1", "kind": "note", "summary": "a", "ts_iso": "2026-01-01T00:00:00+00:00", "meta": {}}
    valid2 = {"id": "e2", "kind": "note", "summary": "b", "ts_iso": "2026-01-02T00:00:00+00:00", "meta": {}}
    episodic.write_text(
        "\n".join([json.dumps(valid1), "{bad json", json.dumps(valid2)]) + "\n",
        encoding="utf-8",
    )

    before = run_doctor(state_dir=tmp_path)
    episodic_before = next(item for item in before.files if item.name == "episodic")
    assert episodic_before.invalid_count == 1

    after = run_doctor(state_dir=tmp_path, repair=True)
    episodic_after = next(item for item in after.files if item.name == "episodic")
    assert episodic_after.invalid_count == 0

    lines = [line for line in episodic.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 2

    backups = list(tmp_path.glob("episodic.jsonl.bak.*"))
    assert backups
