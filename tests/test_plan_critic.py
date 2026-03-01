import json
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from benjamin.apps.api import deps
from benjamin.apps.api.main import app
from benjamin.core.memory.manager import MemoryManager
from benjamin.core.orchestration.orchestrator import Orchestrator


class MockCalendarConnector:
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
        return {
            "id": "evt_critic",
            "title": title,
            "start_iso": start_iso,
            "end_iso": end_iso,
            "html_link": "https://calendar.google.com/event?eid=evt_critic",
        }


class MockEmailConnector:
    def search_messages(self, query: str, max_results: int) -> list[dict]:
        return []

    def read_message(self, message_id: str) -> dict:
        return {}

    def thread_summary(self, thread_id: str, max_messages: int = 10) -> dict:
        return {"thread_id": thread_id, "subject": "", "participants": [], "snippets": []}

    def create_draft(self, to: list[str], cc: list[str] | None, bcc: list[str] | None, subject: str, body: str) -> dict:
        return {"draft_id": "dr_critic", "subject": subject, "to": to, "snippet": body[:24]}


def _setup_client(tmp_path, monkeypatch):
    monkeypatch.setenv("BENJAMIN_TEST_MODE", "1")
    monkeypatch.setenv("BENJAMIN_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("BENJAMIN_APPROVALS_AUTOCLEAN", "off")
    monkeypatch.setenv("BENJAMIN_TIMEZONE", "America/New_York")

    deps.get_memory_manager.cache_clear()
    deps.get_scheduler_service.cache_clear()
    deps.get_orchestrator.cache_clear()
    deps.get_approval_store.cache_clear()
    deps.get_approval_service.cache_clear()

    manager = MemoryManager(state_dir=tmp_path)
    orchestrator = Orchestrator(
        memory_manager=manager,
        calendar_connector=MockCalendarConnector(),
        email_connector=MockEmailConnector(),
    )
    app.dependency_overrides[deps.get_orchestrator] = lambda: orchestrator
    app.dependency_overrides[deps.get_memory_manager] = lambda: manager
    return TestClient(app)


def test_calendar_create_event_with_invalid_end_fails_critic_and_skips_approval(tmp_path, monkeypatch) -> None:
    with _setup_client(tmp_path, monkeypatch) as client:
        payload = {
            "title": "Design review",
            "start_iso": "2026-02-21T14:00:00-05:00",
            "end_iso": "2026-02-21T13:00:00-05:00",
        }
        response = client.post("/chat/", json={"message": f"calendar.create_event {json.dumps(payload)}"})

        assert response.status_code == 200
        assert "What should the correct end time be" in response.json()["response"]

        pending = client.get("/approvals", params={"status": "pending"}).json()["approvals"]
        assert pending == []

    app.dependency_overrides.clear()


def test_calendar_create_event_missing_timezone_is_normalized_and_approval_created(tmp_path, monkeypatch) -> None:
    with _setup_client(tmp_path, monkeypatch) as client:
        payload = {
            "title": "Design review",
            "start_iso": "2026-02-21T14:00:00",
            "end_iso": "2026-02-21T14:30:00",
        }
        response = client.post("/chat/", json={"message": f"calendar.create_event {json.dumps(payload)}"})

        assert response.status_code == 200
        pending = client.get("/approvals", params={"status": "pending"}).json()["approvals"]
        assert len(pending) == 1

        args = json.loads(pending[0]["step"]["args"])
        assert args["timezone"] == "America/New_York"

    app.dependency_overrides.clear()


def test_gmail_draft_email_empty_recipients_fails_critic(tmp_path, monkeypatch) -> None:
    with _setup_client(tmp_path, monkeypatch) as client:
        payload = {
            "to": [],
            "subject": "Status update",
            "body": "Drafting the weekly status update.",
        }
        response = client.post("/chat/", json={"message": f"gmail.draft_email {json.dumps(payload)}"})

        assert response.status_code == 200
        assert "Who should I email?" in response.json()["response"]

        pending = client.get("/approvals", params={"status": "pending"}).json()["approvals"]
        assert pending == []

    app.dependency_overrides.clear()


def test_reminder_in_past_is_normalized_and_approval_created(tmp_path, monkeypatch) -> None:
    with _setup_client(tmp_path, monkeypatch) as client:
        payload = {
            "message": "Stand up",
            "run_at_iso": (datetime.now(tz=timezone.utc) - timedelta(minutes=2)).isoformat(),
        }
        response = client.post("/chat/", json={"message": f"reminders.create {json.dumps(payload)}"})

        assert response.status_code == 200
        pending = client.get("/approvals", params={"status": "pending"}).json()["approvals"]
        assert len(pending) == 1

        args = json.loads(pending[0]["step"]["args"])
        normalized_run_at = datetime.fromisoformat(args["run_at_iso"])
        assert normalized_run_at > datetime.now(tz=timezone.utc)

    app.dependency_overrides.clear()
