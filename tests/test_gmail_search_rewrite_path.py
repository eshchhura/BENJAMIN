import json

from benjamin.core.skills.builtin.gmail_read import GmailSearchSkill


class MockEmailConnector:
    def __init__(self) -> None:
        self.query_used = ""

    def search_messages(self, query: str, max_results: int) -> list[dict]:
        self.query_used = query
        return [{"subject": "A", "snippet": "B", "from": "x", "thread_id": "t"}]


def test_gmail_search_rewrites_nl_query(monkeypatch) -> None:
    monkeypatch.setenv("BENJAMIN_LLM_PROVIDER", "vllm")
    monkeypatch.setenv("BENJAMIN_LLM_RETRIEVAL", "on")

    def fake_complete_text(self, system: str, user: str, max_tokens=None, temperature=None) -> str:
        return "from:alice@example.com newer_than:7d"

    monkeypatch.setattr("benjamin.core.models.llm_provider.BenjaminLLM.complete_text", fake_complete_text)

    connector = MockEmailConnector()
    skill = GmailSearchSkill(connector=connector)
    result = skill.run(json.dumps({"query": "emails from alice", "max_results": 5}))
    payload = json.loads(result.content)

    assert payload["query_used"].startswith("from:alice")
    assert connector.query_used == payload["query_used"]
