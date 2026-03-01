from benjamin.core.memory.manager import MemoryManager
from benjamin.core.orchestration.orchestrator import Orchestrator


def test_planner_uses_llm_when_enabled(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("BENJAMIN_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("BENJAMIN_LLM_PROVIDER", "vllm")
    monkeypatch.setenv("BENJAMIN_LLM_PLANNER", "on")

    def fake_complete_json(self, system: str, user: str, schema_hint: dict | None = None, max_tokens: int | None = None) -> dict:
        return {
            "goal": "read mail",
            "steps": [
                {
                    "description": "Search inbox",
                    "skill_name": "gmail.search",
                    "args": '{"query":"newer_than:1d","max_results":5}',
                    "requires_approval": False,
                }
            ],
        }

    monkeypatch.setattr("benjamin.core.models.llm_provider.BenjaminLLM.complete_json", fake_complete_json)

    orchestrator = Orchestrator(memory_manager=MemoryManager(state_dir=tmp_path))
    result = orchestrator.run("check my inbox")

    events = [event["event"] for event in result.trace_events]
    assert "PlannerSucceeded" in events
    assert result.steps[0].skill_name == "gmail.search"
