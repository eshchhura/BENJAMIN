from pathlib import Path

from core.models.llm import LLMClient
from core.orchestration.orchestrator import Orchestrator
from core.orchestration.schemas import UserRequest


def test_planner_mocked_executes_filesystem_step(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BENJAMIN_LLM_MODE", "http")
    monkeypatch.setenv("BENJAMIN_LLM_HTTP_URL", "http://llm.local/complete")

    def fake_complete_json(self, system_prompt: str, user_prompt: str, json_schema_hint: dict) -> dict:
        _ = (self, system_prompt, user_prompt, json_schema_hint)
        return {
            "steps": [
                {
                    "id": "step-llm-1",
                    "skill_name": "filesystem.search_read",
                    "args": {"query": "banana", "cwd": str(tmp_path), "max_results": 10},
                    "why": "User asked to find banana",
                    "requires_approval": False,
                }
            ]
        }

    monkeypatch.setattr(LLMClient, "complete_json", fake_complete_json)
    (tmp_path / "llm.txt").write_text("there is banana here", encoding="utf-8")

    orchestrator = Orchestrator()
    response = orchestrator.handle(UserRequest(message="can you find banana", cwd=str(tmp_path)))

    event_types = [event.type for event in response.trace.events]
    assert "PlannerAttempted" in event_types
    assert "PlannerSucceeded" in event_types
    assert "Found matches:" in response.answer
    assert "llm.txt" in response.answer
