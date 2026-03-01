from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from benjamin.apps.api import deps
from benjamin.apps.api.main import app
from benjamin.core.runs.schemas import TaskRecord


def _reset_deps() -> None:
    deps.get_memory_manager.cache_clear()
    deps.get_scheduler_service.cache_clear()
    deps.get_orchestrator.cache_clear()
    deps.get_approval_store.cache_clear()
    deps.get_approval_service.cache_clear()
    deps.get_calendar_connector.cache_clear()
    deps.get_email_connector.cache_clear()
    deps.get_notification_router.cache_clear()


def test_ui_runs_q_filter_for_chats(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BENJAMIN_TEST_MODE", "1")
    monkeypatch.setenv("BENJAMIN_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("BENJAMIN_AUTH_MODE", "off")
    _reset_deps()

    with TestClient(app) as client:
        app.state.task_store.append(
            TaskRecord(
                task_id="task-alpha",
                ts_iso=datetime.now(timezone.utc).isoformat(),
                user_message="alpha keyword",
                plan={"steps": []},
                step_results=[],
                approvals_created=[],
                answer="ok",
                trace_events=[],
                correlation_id="corr-alpha",
            )
        )
        app.state.task_store.append(
            TaskRecord(
                task_id="task-beta",
                ts_iso=datetime.now(timezone.utc).isoformat(),
                user_message="beta only",
                plan={"steps": []},
                step_results=[],
                approvals_created=[],
                answer="ok",
                trace_events=[],
                correlation_id="corr-beta",
            )
        )

        response = client.get("/ui/runs", params={"kind": "chat", "q": "alpha", "limit": 10})
        assert response.status_code == 200
        body = response.text
        assert "task-alpha" in body
        assert "task-beta" not in body
        assert "corr-alpha" in body
