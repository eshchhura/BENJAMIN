from __future__ import annotations

import json

from fastapi.testclient import TestClient

from benjamin.apps.api import deps
from benjamin.apps.api.main import app


def _reset_deps() -> None:
    deps.get_memory_manager.cache_clear()
    deps.get_scheduler_service.cache_clear()
    deps.get_orchestrator.cache_clear()
    deps.get_approval_store.cache_clear()
    deps.get_approval_service.cache_clear()


def test_policy_overrides_api_persists(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BENJAMIN_TEST_MODE", "1")
    monkeypatch.setenv("BENJAMIN_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("BENJAMIN_AUTH_MODE", "token")
    monkeypatch.setenv("BENJAMIN_AUTH_TOKEN", "secret")
    monkeypatch.setenv("BENJAMIN_POLICY_OVERRIDES", "on")
    _reset_deps()

    headers = {"X-BENJAMIN-TOKEN": "secret"}
    with TestClient(app) as client:
        enabled_resp = client.post("/v1/security/scopes/enable", json={"scopes": ["calendar.write"]}, headers=headers)
        assert enabled_resp.status_code == 200

        disabled_resp = client.post("/v1/security/scopes/disable", json={"scopes": ["calendar.write"]}, headers=headers)
        assert disabled_resp.status_code == 200

        rules_resp = client.post(
            "/v1/security/rules/allowed-scopes",
            json={"scopes": ["calendar.write", "reminders.write"]},
            headers=headers,
        )
        assert rules_resp.status_code == 200
        snapshot = client.get("/v1/security/scopes", headers=headers).json()["policy"]
        assert "calendar.write" not in snapshot["scopes_enabled"]
        assert set(snapshot["rules_allowed_scopes"]) == {"calendar.write", "reminders.write"}

    overrides = json.loads((tmp_path / "policy_overrides.json").read_text(encoding="utf-8"))
    assert overrides["rules_allowed_scopes"] == ["calendar.write", "reminders.write"]
