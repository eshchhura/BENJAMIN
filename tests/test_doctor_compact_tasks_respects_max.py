from __future__ import annotations

import json

from benjamin.core.ops.doctor import run_doctor


def test_doctor_compact_tasks_respects_max(tmp_path, monkeypatch):
    monkeypatch.setenv("BENJAMIN_TASKS_MAX", "3")
    tasks_path = tmp_path / "tasks.jsonl"
    rows = []
    for idx in range(5):
        rows.append(
            {
                "task_id": f"t-{idx}",
                "ts_iso": f"2026-01-0{idx + 1}T00:00:00+00:00",
                "source": "chat",
                "user_message": "hello",
                "plan": {},
                "step_results": [],
                "approvals_created": [],
                "answer": "ok",
                "trace_events": [],
                "correlation_id": f"c-{idx}",
            }
        )
    tasks_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

    run_doctor(state_dir=tmp_path, compact=True)

    compacted_lines = [line for line in tasks_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(compacted_lines) == 3
    ids = [json.loads(line)["task_id"] for line in compacted_lines]
    assert ids == ["t-2", "t-3", "t-4"]
