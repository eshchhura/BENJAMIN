from benjamin.core.infra.breaker_manager import BreakerManager
from benjamin.core.models.llm_provider import BenjaminLLM
from benjamin.core.orchestration.planner import Planner


def test_planner_falls_back_when_llm_breaker_opens(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("BENJAMIN_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("BENJAMIN_LLM_PROVIDER", "vllm")
    monkeypatch.setenv("BENJAMIN_LLM_PLANNER", "on")
    monkeypatch.setenv("BENJAMIN_BREAKER_FAILURE_THRESHOLD", "1")

    manager = BreakerManager(state_dir=tmp_path)
    llm = BenjaminLLM(breaker_manager=manager)

    def always_fail(**kwargs):
        raise RuntimeError("llm_down")

    monkeypatch.setattr(llm._compat, "chat_completion", always_fail)

    planner = Planner(llm_enabled=True, llm=llm)
    plan = planner.plan("check inbox quickly")

    assert plan.goal == "check inbox quickly"
    assert len(plan.steps) >= 1
    assert manager.snapshot()["llm"]["state"] == "open"
