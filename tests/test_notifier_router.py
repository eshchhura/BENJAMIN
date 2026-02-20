from core.memory.manager import MemoryManager
from core.notifications.notifier import NotificationRouter
from core.scheduler.jobs import run_daily_briefing, run_reminder


class RecorderNotifier:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    def send(self, title: str, body: str, meta: dict | None = None) -> None:
        self.messages.append({"title": title, "body": body, "meta": meta or {}})


def test_jobs_send_notifications_and_append_episodic_memory(tmp_path) -> None:
    memory = MemoryManager(state_dir=tmp_path)
    memory.semantic.upsert(key="preference:timezone", value="EST", scope="global", tags=["preference"])
    memory.episodic.append(kind="note", summary="alpha")

    notifier = RecorderNotifier()
    router = NotificationRouter(channels=[notifier])

    run_reminder(message="Water plants", state_dir=str(tmp_path), job_id="reminder:test", router=router)
    run_daily_briefing(state_dir=str(tmp_path), job_id="daily-briefing", router=router)

    assert [message["title"] for message in notifier.messages] == ["Reminder", "Daily Briefing"]
    recent = memory.episodic.list_recent(limit=5)
    summaries = [episode.summary for episode in recent]
    assert any(summary.startswith("Sent reminder:") for summary in summaries)
    assert any(summary == "Sent daily briefing" for summary in summaries)
