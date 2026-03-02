from __future__ import annotations

import json

from fastapi.testclient import TestClient

from benjamin.apps.api import deps
from benjamin.apps.api.main import app


def _clear_dependency_caches() -> None:
    deps.get_memory_manager.cache_clear()
    deps.get_calendar_connector.cache_clear()
    deps.get_email_connector.cache_clear()
    deps.get_scheduler_service.cache_clear()
    deps.get_orchestrator.cache_clear()
    deps.get_notification_router.cache_clear()


def test_maintenance_status_defaults(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BENJAMIN_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("BENJAMIN_TEST_MODE", "on")
    _clear_dependency_caches()

    with TestClient(app) as client:
        response = client.get("/v1/ops/maintenance")

    assert response.status_code == 200
    payload = response.json()
    assert payload["doctor_validate"]["last_run_iso"] is None
    assert payload["weekly_compact"]["last_run_iso"] is None


def test_run_doctor_now_writes_status_and_episode(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BENJAMIN_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("BENJAMIN_TEST_MODE", "on")
    _clear_dependency_caches()

    (tmp_path / "tasks.jsonl").write_text('{"task_id": "bad"\n', encoding="utf-8")

    with TestClient(app) as client:
        response = client.post("/v1/ops/maintenance/run-doctor-now")

    assert response.status_code == 200
    status_path = tmp_path / "maintenance.json"
    status_payload = json.loads(status_path.read_text(encoding="utf-8"))
    assert status_payload["doctor_validate"]["last_run_iso"]
    assert status_payload["doctor_validate"]["ok"] is False
    assert status_payload["doctor_validate"]["correlation_id"]

    episodes = (tmp_path / "episodic.jsonl").read_text(encoding="utf-8").splitlines()
    maintenance_entries = [json.loads(line) for line in episodes if line.strip()]
    assert any(entry["kind"] == "maintenance" and entry["meta"]["job"] == "doctor_validate" for entry in maintenance_entries)


def test_run_compact_now_trims_tasks(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BENJAMIN_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("BENJAMIN_TEST_MODE", "on")
    monkeypatch.setenv("BENJAMIN_TASKS_MAX", "3")
    _clear_dependency_caches()

    rows = []
    for idx in range(5):
        rows.append(
            {
                "task_id": f"task-{idx}",
                "ts_iso": f"2026-01-0{idx + 1}T00:00:00+00:00",
                "source": "chat",
                "user_message": "hello",
                "plan": {},
                "step_results": [],
                "approvals_created": [],
                "answer": "ok",
                "trace_events": [],
                "correlation_id": f"corr-{idx}",
            }
        )
    (tmp_path / "tasks.jsonl").write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

    with TestClient(app) as client:
        response = client.post("/v1/ops/maintenance/run-compact-now")

    assert response.status_code == 200
    lines = [line for line in (tmp_path / "tasks.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 3
    status_payload = json.loads((tmp_path / "maintenance.json").read_text(encoding="utf-8"))
    assert status_payload["weekly_compact"]["last_run_iso"]


def test_ui_ops_renders(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BENJAMIN_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("BENJAMIN_TEST_MODE", "on")
    _clear_dependency_caches()

    with TestClient(app) as client:
        response = client.get("/ui/ops")

    assert response.status_code == 200
    assert "Maintenance" in response.text
    assert "Last run" in response.text
