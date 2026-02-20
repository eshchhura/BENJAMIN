from core.orchestration.orchestrator import Orchestrator


def test_orchestrator_runs_plan_steps() -> None:
    result = Orchestrator().run("draft release notes")

    assert len(result.steps) == 2
    assert result.outputs[-1].startswith("done:")
