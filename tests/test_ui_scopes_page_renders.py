from __future__ import annotations

from fastapi.testclient import TestClient

from benjamin.apps.api import deps
from benjamin.apps.api.main import app


def _reset_deps() -> None:
    deps.get_memory_manager.cache_clear()
    deps.get_scheduler_service.cache_clear()
    deps.get_orchestrator.cache_clear()
    deps.get_approval_store.cache_clear()
    deps.get_approval_service.cache_clear()


def test_ui_scopes_page_renders(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BENJAMIN_TEST_MODE", "1")
    monkeypatch.setenv("BENJAMIN_STATE_DIR", str(tmp_path))
    _reset_deps()

    with TestClient(app) as client:
        response = client.get("/ui/scopes")
    assert response.status_code == 200
    assert "filesystem.read" in response.text
