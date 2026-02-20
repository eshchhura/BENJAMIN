from __future__ import annotations

from pathlib import Path

from core.memory.manager import MemoryManager
from core.notifications.notifier import NotificationRouter, build_notification_router


def _memory_manager_for_state(state_dir: str) -> MemoryManager:
    return MemoryManager(state_dir=Path(state_dir))


def run_reminder(
    message: str,
    state_dir: str,
    job_id: str | None = None,
    router: NotificationRouter | None = None,
) -> None:
    active_router = router or build_notification_router()
    active_router.send(title="Reminder", body=message, meta={"job_id": job_id} if job_id else {})

    memory = _memory_manager_for_state(state_dir)
    memory.episodic.append(
        kind="notification",
        summary=f"Sent reminder: {message}",
        meta={"job_id": job_id} if job_id else {},
    )


def run_daily_briefing(
    state_dir: str,
    job_id: str | None = None,
    router: NotificationRouter | None = None,
) -> None:
    memory = _memory_manager_for_state(state_dir)
    recent_events = memory.episodic.list_recent(limit=3)
    preferences = [
        fact for fact in memory.semantic.list_all(scope="global") if fact.key.startswith("preference:")
    ][:5]

    event_lines = [f"- {event.summary}" for event in recent_events] or ["- No recent events"]
    preference_lines = [f"- {fact.key}: {fact.value}" for fact in preferences] or ["- No saved preferences"]
    body = "\n".join(
        [
            "Recent episodes:",
            *event_lines,
            "",
            "Top preferences:",
            *preference_lines,
        ]
    )

    active_router = router or build_notification_router()
    active_router.send(title="Daily Briefing", body=body, meta={"job_id": job_id} if job_id else {})

    memory.episodic.append(
        kind="briefing",
        summary="Sent daily briefing",
        meta={
            "job_id": job_id,
            "items": {
                "recent_events": [event.summary for event in recent_events],
                "preferences": [f"{fact.key}:{fact.value}" for fact in preferences],
            },
        },
    )
