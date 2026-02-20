from pathlib import Path

from core.orchestration.orchestrator import Orchestrator
from core.orchestration.schemas import UserRequest


def test_planner_bypassed_when_llm_off(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("BENJAMIN_LLM_MODE", raising=False)
    monkeypatch.delenv("BENJAMIN_LLM_HTTP_URL", raising=False)
    monkeypatch.delenv("BENJAMIN_LLM_HTTP_TOKEN", raising=False)

    (tmp_path / "sample.txt").write_text("banana world", encoding="utf-8")

    orchestrator = Orchestrator()
    response = orchestrator.handle(UserRequest(message="search banana", cwd=str(tmp_path)))

    event_types = [event.type for event in response.trace.events]
    assert "PlannerAttempted" not in event_types
    assert "Found matches:" in response.answer
    assert "sample.txt" in response.answer
