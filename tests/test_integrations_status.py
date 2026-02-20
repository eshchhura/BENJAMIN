from fastapi.testclient import TestClient

from benjamin.apps.api import deps
from benjamin.apps.api.main import app


def test_integrations_status_defaults_google_off(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BENJAMIN_STATE_DIR", str(tmp_path))
    monkeypatch.delenv("BENJAMIN_GOOGLE_ENABLED", raising=False)

    deps.get_memory_manager.cache_clear()
    deps.get_calendar_connector.cache_clear()
    deps.get_email_connector.cache_clear()

    with TestClient(app) as client:
        response = client.get("/integrations/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["google_enabled"] is False
    assert payload["calendar_ready"] is False
    assert payload["gmail_ready"] is False
    assert payload["google_token_present"] is False
