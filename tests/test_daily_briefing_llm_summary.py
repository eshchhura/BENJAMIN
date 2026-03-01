from benjamin.core.scheduler.jobs import run_daily_briefing


class CaptureChannel:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str]] = []

    def send(self, title: str, body: str, meta: dict | None = None) -> None:
        self.messages.append((title, body))


class MockCalendarConnector:
    def search_events(self, calendar_id: str, time_min_iso: str, time_max_iso: str, query: str | None, max_results: int) -> list[dict]:
        return [{"title": "Standup", "start_iso": "2026-01-01T09:00:00Z"}]


class MockEmailConnector:
    def search_messages(self, query: str, max_results: int) -> list[dict]:
        return [{"subject": "Status", "snippet": "All good", "thread_id": "thr-1"}]

    def thread_summary(self, thread_id: str, max_messages: int = 10) -> dict:
        return {"snippets": ["Thread summary"]}


def test_daily_briefing_uses_summarizer(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("BENJAMIN_LLM_PROVIDER", "vllm")
    monkeypatch.setenv("BENJAMIN_LLM_SUMMARIZER", "on")

    def fake_complete_text(self, system: str, user: str, max_tokens=None, temperature=None) -> str:
        return "Prioritized briefing output"

    monkeypatch.setattr("benjamin.core.models.llm_provider.BenjaminLLM.complete_text", fake_complete_text)

    channel = CaptureChannel()
    from benjamin.core.notifications.notifier import NotificationRouter

    run_daily_briefing(
        state_dir=str(tmp_path),
        router=NotificationRouter(channels=[channel]),
        calendar_connector=MockCalendarConnector(),
        email_connector=MockEmailConnector(),
    )

    assert channel.messages
    assert "Prioritized briefing output" in channel.messages[0][1]
