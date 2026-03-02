from fastapi.testclient import TestClient

from benjamin.apps.api import deps
from benjamin.apps.api.main import app


def _reset_deps() -> None:
    deps.get_memory_manager.cache_clear()
    deps.get_scheduler_service.cache_clear()
    deps.get_orchestrator.cache_clear()
    deps.get_approval_store.cache_clear()
    deps.get_approval_service.cache_clear()


def test_ui_shows_safe_mode_banner(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BENJAMIN_TEST_MODE", "1")
    monkeypatch.setenv("BENJAMIN_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("BENJAMIN_SAFE_MODE", "on")
    monkeypatch.setenv("BENJAMIN_AUTH_MODE", "off")
    _reset_deps()

    with TestClient(app) as client:
        response = client.get("/ui/runs")
        assert response.status_code == 200
        assert "SAFE MODE ENABLED: write actions and approvals are disabled." in response.text
