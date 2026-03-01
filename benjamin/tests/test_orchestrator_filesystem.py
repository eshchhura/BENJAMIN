from pathlib import Path

from benjamin.core.orchestration.orchestrator import Orchestrator
from benjamin.core.orchestration.schemas import UserRequest


def test_orchestrator_searches_filesystem(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("apple\nbanana split\ncarrot", encoding="utf-8")
    (tmp_path / "b.txt").write_text("nothing here", encoding="utf-8")

    orchestrator = Orchestrator()
    response = orchestrator.handle(UserRequest(message="search banana", cwd=str(tmp_path)))

    assert "Found matches:" in response.answer
    assert "a.txt" in response.answer
    assert any(event.type == "StepFinished" for event in response.trace.events)
