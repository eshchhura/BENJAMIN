import json

from fastapi.testclient import TestClient

from benjamin.apps.api import deps
from benjamin.apps.api.main import app
from benjamin.core.memory.manager import MemoryManager
from benjamin.core.orchestration.orchestrator import Orchestrator


class MockCalendarConnector:
    def __init__(self) -> None:
        self.called = False

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
        self.called = True
        return {
            "id": "evt_123",
            "title": title,
            "start_iso": start_iso,
            "end_iso": end_iso,
            "html_link": "https://calendar.google.com/event?eid=evt_123",
        }


class MockEmailConnector:
    def search_messages(self, query: str, max_results: int) -> list[dict]:
        return []

    def read_message(self, message_id: str) -> dict:
        return {}

    def thread_summary(self, thread_id: str, max_messages: int = 10) -> dict:
        return {"thread_id": thread_id, "subject": "", "participants": [], "snippets": []}

    def create_draft(self, to: list[str], cc: list[str] | None, bcc: list[str] | None, subject: str, body: str) -> dict:
        return {"draft_id": "unused", "subject": subject, "to": to, "snippet": body[:20]}


def test_calendar_create_event_is_approval_gated_and_executes_after_approve(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BENJAMIN_TEST_MODE", "1")
    monkeypatch.setenv("BENJAMIN_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("BENJAMIN_APPROVALS_AUTOCLEAN", "off")

    deps.get_memory_manager.cache_clear()
    deps.get_scheduler_service.cache_clear()
    deps.get_orchestrator.cache_clear()
    deps.get_approval_store.cache_clear()
    deps.get_approval_service.cache_clear()

    memory_manager = MemoryManager(state_dir=tmp_path)
    mock_calendar = MockCalendarConnector()
    orchestrator = Orchestrator(
        memory_manager=memory_manager,
        calendar_connector=mock_calendar,
        email_connector=MockEmailConnector(),
    )
    app.dependency_overrides[deps.get_orchestrator] = lambda: orchestrator
    app.dependency_overrides[deps.get_memory_manager] = lambda: memory_manager

    payload = {
        "title": "Design review",
        "start_iso": "2026-02-21T14:00:00-05:00",
        "end_iso": "2026-02-21T14:30:00-05:00",
    }

    with TestClient(app) as client:
        chat_response = client.post("/chat/", json={"message": f"calendar.create_event {json.dumps(payload)}"})
        assert chat_response.status_code == 200
        assert not mock_calendar.called

        approvals = client.get("/approvals", params={"status": "pending"}).json()["approvals"]
        assert len(approvals) == 1
        approval_id = approvals[0]["id"]

        approve_response = client.post(f"/approvals/{approval_id}/approve", json={"approver_note": "approved"})
        assert approve_response.status_code == 200
        approved = approve_response.json()
        assert approved["status"] == "approved"
        assert approved["result"]["ok"] is True
        assert approved["result"]["output"]
        assert approved["error"] is None
        assert mock_calendar.called

        episodic = client.get("/memory/episodic", params={"limit": 20}).json()["items"]
        assert any(item["kind"] == "approval" and item["meta"].get("approval_id") == approval_id for item in episodic)

    app.dependency_overrides.clear()


def test_calendar_create_event_approval_gracefully_fails_without_integration(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BENJAMIN_TEST_MODE", "1")
    monkeypatch.setenv("BENJAMIN_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("BENJAMIN_APPROVALS_AUTOCLEAN", "off")

    deps.get_memory_manager.cache_clear()
    deps.get_scheduler_service.cache_clear()
    deps.get_orchestrator.cache_clear()
    deps.get_approval_store.cache_clear()
    deps.get_approval_service.cache_clear()

    with TestClient(app) as client:
        payload = {
            "title": "Design review",
            "start_iso": "2026-02-21T14:00:00-05:00",
            "end_iso": "2026-02-21T14:30:00-05:00",
        }
        chat_response = client.post("/chat/", json={"message": f"calendar.create_event {json.dumps(payload)}"})
        assert chat_response.status_code == 200

        approval_id = client.get("/approvals", params={"status": "pending"}).json()["approvals"][0]["id"]
        approve_response = client.post(f"/approvals/{approval_id}/approve", json={"approver_note": "ok"})
        assert approve_response.status_code == 200
        approved = approve_response.json()
        assert approved["status"] == "approved"
        assert approved["result"]["ok"] is False
        assert approved["error"] == "calendar_integration_unavailable"
