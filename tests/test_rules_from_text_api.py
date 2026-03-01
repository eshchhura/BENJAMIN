from fastapi.testclient import TestClient

from benjamin.apps.api import deps
from benjamin.apps.api.main import app


def _reset_deps() -> None:
    deps.get_memory_manager.cache_clear()
    deps.get_scheduler_service.cache_clear()
    deps.get_orchestrator.cache_clear()
    deps.get_approval_store.cache_clear()
    deps.get_approval_service.cache_clear()
    deps.get_calendar_connector.cache_clear()
    deps.get_email_connector.cache_clear()
    deps.get_notification_router.cache_clear()


def test_rules_from_text_returns_preview(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("BENJAMIN_TEST_MODE", "1")
    monkeypatch.setenv("BENJAMIN_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("BENJAMIN_LLM_PROVIDER", "vllm")
    monkeypatch.setenv("BENJAMIN_LLM_RULE_BUILDER", "on")
    _reset_deps()

    def fake_complete_json(self, system: str, user: str, schema_hint=None, max_tokens=None):
        return {
            "name": "rule via nl",
            "trigger": {"type": "schedule", "every_minutes": 5},
            "condition": {"contains": "invoice"},
            "actions": [{"type": "notify", "title": "Invoices", "body_template": "Matched {{count}}"}],
            "cooldown_minutes": 1,
            "max_actions_per_run": 1,
        }

    monkeypatch.setattr("benjamin.core.models.llm_provider.BenjaminLLM.complete_json", fake_complete_json)

    with TestClient(app) as client:
        response = client.post("/rules/from-text", json={"text": "alert me about invoices"})
        assert response.status_code == 200
        payload = response.json()
        assert payload["ok"] is True
        assert payload["rule_preview"]["name"] == "rule via nl"


def test_rules_from_text_invalid_returns_error(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("BENJAMIN_TEST_MODE", "1")
    monkeypatch.setenv("BENJAMIN_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("BENJAMIN_LLM_PROVIDER", "vllm")
    monkeypatch.setenv("BENJAMIN_LLM_RULE_BUILDER", "on")
    _reset_deps()

    def fake_complete_json(self, system: str, user: str, schema_hint=None, max_tokens=None):
        return {"bad": "payload"}

    monkeypatch.setattr("benjamin.core.models.llm_provider.BenjaminLLM.complete_json", fake_complete_json)

    with TestClient(app) as client:
        response = client.post("/rules/from-text", json={"text": "bad"})
        assert response.status_code == 200
        assert response.json()["ok"] is False
