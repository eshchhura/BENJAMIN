from fastapi.testclient import TestClient

from benjamin.apps.api import deps
from benjamin.apps.api.main import app


def _reset_deps() -> None:
    deps.get_memory_manager.cache_clear()
    deps.get_scheduler_service.cache_clear()
    deps.get_orchestrator.cache_clear()
    deps.get_approval_store.cache_clear()
    deps.get_approval_service.cache_clear()


def test_safe_mode_disables_planner_llm(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("BENJAMIN_TEST_MODE", "1")
    monkeypatch.setenv("BENJAMIN_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("BENJAMIN_SAFE_MODE", "on")
    monkeypatch.setenv("BENJAMIN_LLM_PROVIDER", "vllm")
    monkeypatch.setenv("BENJAMIN_LLM_PLANNER", "on")

    def explode(*args, **kwargs):
        raise AssertionError("planner llm should not be called in safe mode")

    monkeypatch.setattr("benjamin.core.models.llm_provider.BenjaminLLM.complete_json", explode)
    _reset_deps()

    with TestClient(app) as client:
        response = client.post("/chat/", json={"message": "check my inbox"})
        assert response.status_code == 200
        assert response.json()["response"]

    orchestrator = deps.get_orchestrator()
    result = orchestrator.run("check my inbox")
    assert result.steps[0].description.startswith("Analyze:")
    assert not any(event["event"] == "PlannerAttempted" for event in result.trace_events)
