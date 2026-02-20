import json

from benjamin.core.skills.builtin.gmail_read import GmailSearchSkill, GmailThreadSummarySkill


class MockEmailConnector:
    def search_messages(self, query: str, max_results: int) -> list[dict]:
        assert "newer_than" in query
        assert max_results == 5
        return [
            {
                "id": "msg-1",
                "thread_id": "thread-1",
                "from": "alice@example.com",
                "subject": "Quarterly planning",
                "snippet": "Please review the attached agenda",
                "date_iso": "2026-02-21T14:00:00+00:00",
            }
        ]

    def read_message(self, message_id: str) -> dict:
        return {}

    def thread_summary(self, thread_id: str, max_messages: int = 10) -> dict:
        assert thread_id == "thread-1"
        return {
            "thread_id": "thread-1",
            "subject": "Quarterly planning",
            "participants": ["alice@example.com", "me@example.com"],
            "snippets": ["Agenda draft", "Final timing"],
        }


def test_gmail_search_and_thread_summary_skills_with_mock() -> None:
    connector = MockEmailConnector()
    search_skill = GmailSearchSkill(connector=connector)
    summary_skill = GmailThreadSummarySkill(connector=connector)

    search_payload = json.loads(search_skill.run(json.dumps({"query": "newer_than:1d", "max_results": 5})).content)
    assert search_payload["messages"][0]["subject"] == "Quarterly planning"

    summary_payload = json.loads(summary_skill.run(json.dumps({"thread_id": "thread-1", "max_messages": 3})).content)
    assert summary_payload["participants"] == ["alice@example.com", "me@example.com"]
    assert summary_payload["snippets"][0] == "Agenda draft"
