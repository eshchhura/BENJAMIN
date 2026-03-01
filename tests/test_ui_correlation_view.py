from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from benjamin.apps.api import deps
from benjamin.apps.api.main import app
from benjamin.core.approvals.schemas import PendingApproval
from benjamin.core.ledger.keys import approval_execution_key
from benjamin.core.orchestration.schemas import PlanStep
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


def test_ui_correlation_view_aggregates_linked_records(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BENJAMIN_TEST_MODE", "1")
    monkeypatch.setenv("BENJAMIN_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("BENJAMIN_AUTH_MODE", "off")
    monkeypatch.setenv("BENJAMIN_APPROVALS_AUTOCLEAN", "off")
    _reset_deps()

    correlation_id = "corr-123"
    task_id = "task-corr"
    approval_id = "approval-corr"

    with TestClient(app) as client:
        task = TaskRecord(
            task_id=task_id,
            ts_iso=datetime.now(timezone.utc).isoformat(),
            user_message="run correlation test",
            plan={"steps": []},
            step_results=[],
            approvals_created=[approval_id],
            answer="done",
            trace_events=[],
            correlation_id=correlation_id,
        )
        app.state.task_store.append(task)
        app.state.memory_manager.episodic.append(
            kind="approval",
            summary="episode tied to corr",
            meta={"correlation_id": correlation_id, "approval_id": approval_id},
        )

        key = approval_execution_key(approval_id, PlanStep(id="s1", description="send", skill_name="gmail_write", args="{}"))
        app.state.approval_service.ledger.try_start(
            key=key,
            kind="approval_exec",
            correlation_id=correlation_id,
            meta={"approval_id": approval_id},
        )

        approval = PendingApproval(
            id=approval_id,
            created_at_iso=datetime.now(timezone.utc).isoformat(),
            expires_at_iso=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            status="pending",
            requester={"correlation_id": correlation_id},
            step=PlanStep(id="s1", description="send", skill_name="gmail_write", args="{\"to\": \"x@y.com\"}"),
            context={"goal": "test"},
            rationale="test rationale",
        )
        app.state.approval_service.store.upsert(approval)

        response = client.get(f"/ui/correlation/{correlation_id}")
        assert response.status_code == 200
        body = response.text
        assert correlation_id in body
        assert task_id in body
        assert approval_id in body
        assert key[:12] in body
        assert "episode tied to corr" in body
