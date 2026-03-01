import json
from datetime import datetime, timedelta, timezone

from benjamin.core.memory.manager import MemoryManager
from benjamin.core.orchestration.orchestrator import Orchestrator
from benjamin.core.orchestration.schemas import ChatRequest


def test_disabled_scope_blocks_and_creates_no_approval(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BENJAMIN_SCOPE_MODE", "allowlist")
    monkeypatch.setenv("BENJAMIN_SCOPES_ENABLED", "gmail.read")

    manager = MemoryManager(state_dir=tmp_path)
    orchestrator = Orchestrator(memory_manager=manager)
    payload = {
        "message": "Pay rent",
        "run_at_iso": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
    }

    result = orchestrator.handle(ChatRequest(message=f"reminders.create {json.dumps(payload)}"))

    assert result.step_results[0].ok is False
    assert result.step_results[0].error.startswith("policy_denied:")
    assert orchestrator.approval_service.store.list_all(status="pending") == []
