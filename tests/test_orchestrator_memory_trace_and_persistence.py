from core.memory.manager import MemoryManager
from core.orchestration.orchestrator import Orchestrator
from core.orchestration.schemas import ChatRequest


def _get_event(result, name: str):
    return next(event for event in result.trace_events if event["event"] == name)


def test_orchestrator_memory_trace_and_persistence(tmp_path) -> None:
    manager_a = MemoryManager(state_dir=tmp_path)
    orchestrator_a = Orchestrator(memory_manager=manager_a)

    first = orchestrator_a.handle(ChatRequest(message="Plan my day"))
    first_commit = _get_event(first, "MemoryWriteCommitted")
    assert first_commit["payload"]["episodic_count"] == 1

    manager_b = MemoryManager(state_dir=tmp_path)
    orchestrator_b = Orchestrator(memory_manager=manager_b)
    second = orchestrator_b.handle(ChatRequest(message="Plan my day"))

    retrieved = _get_event(second, "MemoryRetrieved")
    assert retrieved["payload"]["episodic_count"] >= 1
