from __future__ import annotations

from benjamin.core.memory.manager import MemoryManager
from benjamin.core.orchestration.orchestrator import Orchestrator
from benjamin.core.orchestration.schemas import ChatRequest


def test_policy_telemetry_episode_written(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BENJAMIN_SCOPE_MODE", "allowlist")
    monkeypatch.setenv("BENJAMIN_SCOPES_ENABLED", "")

    memory = MemoryManager(state_dir=tmp_path)
    orchestrator = Orchestrator(memory_manager=memory)
    orchestrator.handle(ChatRequest(message='reminders.create {"message":"x","run_at_iso":"2030-01-01T10:00:00+00:00"}'))

    policy_episodes = [ep for ep in memory.episodic.list_recent(limit=50) if ep.kind == "policy"]
    assert policy_episodes
    meta = policy_episodes[0].meta
    assert meta.get("correlation_id")
    assert "required_scopes" in meta
