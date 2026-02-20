import json
from datetime import datetime, timedelta, timezone

from benjamin.core.memory.manager import MemoryManager
from benjamin.core.orchestration.orchestrator import Orchestrator
from benjamin.core.orchestration.schemas import ChatRequest


def test_executor_creates_approval_for_write_step(tmp_path) -> None:
    manager = MemoryManager(state_dir=tmp_path)
    orchestrator = Orchestrator(memory_manager=manager)
    payload = {
        "message": "Submit report",
        "run_at_iso": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
    }
    request = ChatRequest(message=f"reminders.create {json.dumps(payload)}")

    result = orchestrator.handle(request)

    assert result.step_results[0].error.startswith("approval_required:")
    approval_id = result.step_results[0].error.split(":", 1)[1]

    pending = orchestrator.approval_service.store.get(approval_id)
    assert pending is not None
    assert pending.status == "pending"

    approval_event = next(event for event in result.trace_events if event["event"] == "ApprovalRequired")
    assert approval_event["payload"]["approval_id"] == approval_id
