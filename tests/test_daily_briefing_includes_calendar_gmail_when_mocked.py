from benjamin.core.memory.manager import MemoryManager
from benjamin.core.notifications.notifier import NotificationRouter
from benjamin.core.scheduler.jobs import run_daily_briefing


class RecorderNotifier:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    def send(self, title: str, body: str, meta: dict | None = None) -> None:
        self.messages.append({"title": title, "body": body, "meta": meta or {}})


class MockCalendarConnector:
    def search_events(self, calendar_id: str, time_min_iso: str, time_max_iso: str, query: str | None, max_results: int) -> list[dict]:
        return [{"title": "Standup", "start_iso": "2026-02-21T09:00:00-05:00", "end_iso": "2026-02-21T09:15:00-05:00"}]


class MockEmailConnector:
    def search_messages(self, query: str, max_results: int) -> list[dict]:
        return [{"thread_id": "t1", "subject": "Ship it", "snippet": "Looks good"}]

    def read_message(self, message_id: str) -> dict:
        return {}

    def thread_summary(self, thread_id: str, max_messages: int = 10) -> dict:
        return {"thread_id": thread_id, "subject": "Ship it", "participants": ["a@example.com"], "snippets": ["Merged"]}


def test_daily_briefing_includes_calendar_and_email_sections(tmp_path) -> None:
    memory = MemoryManager(state_dir=tmp_path)
    memory.episodic.append(kind="note", summary="yesterday recap")

    recorder = RecorderNotifier()
    router = NotificationRouter(channels=[recorder])

    run_daily_briefing(
        state_dir=str(tmp_path),
        job_id="daily-briefing",
        router=router,
        calendar_connector=MockCalendarConnector(),
        email_connector=MockEmailConnector(),
    )

    body = recorder.messages[-1]["body"]
    assert "Today's schedule:" in body
    assert "Important emails:" in body

    latest = memory.episodic.list_recent(limit=1)[0]
    assert latest.meta["calendar_included"] is True
    assert latest.meta["gmail_included"] is True
