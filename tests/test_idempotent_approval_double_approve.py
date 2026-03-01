import json

from fastapi.testclient import TestClient

from benjamin.apps.api import deps
from benjamin.apps.api.main import app
from benjamin.core.ledger.keys import approval_execution_key
from benjamin.core.ledger.ledger import ExecutionLedger
from benjamin.core.memory.manager import MemoryManager
from benjamin.core.orchestration.orchestrator import Orchestrator
from benjamin.core.orchestration.schemas import PlanStep


class CountingCalendarConnector:
    def __init__(self) -> None:
        self.create_event_calls = 0

    def search_events(self, calendar_id: str, time_min_iso: str, time_max_iso: str, query: str | None, max_results: int) -> list[dict]:
        return []

    def create_event(
        self,
        calendar_id: str,
        title: str,
        start_iso: str,
        end_iso: str,
        timezone: str,
        location: str | None,
        description: str | None,
        attendees: list[str] | None,
    ) -> dict:
        self.create_event_calls += 1
        return {"id": "evt_1", "title": title, "start_iso": start_iso, "end_iso": end_iso}


class NoopEmailConnector:
    def search_messages(self, query: str, max_results: int) -> list[dict]:
        return []

    def read_message(self, message_id: str) -> dict:
        return {}

    def thread_summary(self, thread_id: str, max_messages: int = 10) -> dict:
        return {"thread_id": thread_id, "subject": "", "participants": [], "snippets": []}

    def create_draft(self, to: list[str], cc: list[str] | None, bcc: list[str] | None, subject: str, body: str) -> dict:
        return {"draft_id": "draft_1"}


def _reset_deps() -> None:
    deps.get_memory_manager.cache_clear()
    deps.get_scheduler_service.cache_clear()
    deps.get_orchestrator.cache_clear()
    deps.get_approval_store.cache_clear()
    deps.get_approval_service.cache_clear()


def test_approving_same_approval_twice_is_idempotent(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BENJAMIN_TEST_MODE", "1")
    monkeypatch.setenv("BENJAMIN_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("BENJAMIN_APPROVALS_AUTOCLEAN", "off")
    _reset_deps()

    memory_manager = MemoryManager(state_dir=tmp_path)
    calendar = CountingCalendarConnector()
    orchestrator = Orchestrator(memory_manager=memory_manager, calendar_connector=calendar, email_connector=NoopEmailConnector())

    app.dependency_overrides[deps.get_orchestrator] = lambda: orchestrator
    app.dependency_overrides[deps.get_memory_manager] = lambda: memory_manager

    payload = {
        "title": "Idempotency check",
        "start_iso": "2026-02-21T14:00:00-05:00",
        "end_iso": "2026-02-21T14:30:00-05:00",
    }

    with TestClient(app) as client:
        chat_response = client.post("/chat/", json={"message": f"calendar.create_event {json.dumps(payload)}"})
        assert chat_response.status_code == 200

        approval = client.get("/approvals", params={"status": "pending"}).json()["approvals"][0]
        approval_id = approval["id"]

        first = client.post(f"/approvals/{approval_id}/approve", json={"approver_note": "ok"})
        second = client.post(f"/approvals/{approval_id}/approve", json={"approver_note": "ok again"})

        assert first.status_code == 200
        assert second.status_code == 200
        assert calendar.create_event_calls == 1

        second_json = second.json()
        assert second_json["status"] == "approved"
        assert "idempotent_duplicate" in (second_json["result"]["output"] or "")

        step = PlanStep.model_validate(second_json["step"])
        key = approval_execution_key(approval_id=approval_id, step=step)
        ledger = ExecutionLedger(tmp_path)
        assert ledger.has_succeeded(key) is True

    app.dependency_overrides.clear()
