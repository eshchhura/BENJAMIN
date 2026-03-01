import json

from fastapi.testclient import TestClient

from benjamin.apps.api import deps
from benjamin.apps.api.main import app
from benjamin.core.memory.manager import MemoryManager
from benjamin.core.orchestration.orchestrator import Orchestrator


class MockEmailConnector:
    def __init__(self) -> None:
        self.calls = 0

    def search_messages(self, query: str, max_results: int) -> list[dict]:
        return []

    def read_message(self, message_id: str) -> dict:
        return {}

    def thread_summary(self, thread_id: str, max_messages: int = 10) -> dict:
        return {"thread_id": thread_id, "subject": "", "participants": [], "snippets": []}

    def create_draft(self, to: list[str], cc: list[str] | None, bcc: list[str] | None, subject: str, body: str) -> dict:
        self.calls += 1
        return {"draft_id": "dr_1", "subject": subject, "to": to, "snippet": body[:20]}


def test_enabled_write_scope_allows_approval_and_execution(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BENJAMIN_TEST_MODE", "1")
    monkeypatch.setenv("BENJAMIN_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("BENJAMIN_APPROVALS_AUTOCLEAN", "off")
    monkeypatch.setenv("BENJAMIN_SCOPE_MODE", "allowlist")
    monkeypatch.setenv("BENJAMIN_SCOPES_ENABLED", "gmail.draft")

    deps.get_memory_manager.cache_clear()
    deps.get_scheduler_service.cache_clear()
    deps.get_orchestrator.cache_clear()
    deps.get_approval_store.cache_clear()
    deps.get_approval_service.cache_clear()

    memory_manager = MemoryManager(state_dir=tmp_path)
    email = MockEmailConnector()
    orchestrator = Orchestrator(memory_manager=memory_manager, email_connector=email)

    app.dependency_overrides[deps.get_orchestrator] = lambda: orchestrator
    app.dependency_overrides[deps.get_memory_manager] = lambda: memory_manager

    payload = {"to": ["alex@example.com"], "subject": "Status", "body": "Draft this update please."}
    with TestClient(app) as client:
        chat = client.post("/chat/", json={"message": f"gmail.draft_email {json.dumps(payload)}"})
        assert chat.status_code == 200
        approval_id = client.get("/approvals", params={"status": "pending"}).json()["approvals"][0]["id"]
        approved = client.post(f"/approvals/{approval_id}/approve", json={"approver_note": "ok"})
        assert approved.status_code == 200
        assert approved.json()["result"]["ok"] is True

    assert email.calls == 1
    app.dependency_overrides.clear()
