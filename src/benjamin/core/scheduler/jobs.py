from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from uuid import uuid4

from benjamin.core.integrations.base import CalendarConnector, EmailConnector
from benjamin.core.memory.manager import MemoryManager
from benjamin.core.notifications.notifier import NotificationRouter, build_notification_router


def _memory_manager_for_state(state_dir: str) -> MemoryManager:
    return MemoryManager(state_dir=Path(state_dir))


def _build_default_connectors(state_dir: str) -> tuple[CalendarConnector | None, EmailConnector | None]:
    if os.getenv("BENJAMIN_GOOGLE_ENABLED", "off").casefold() != "on":
        return None, None

    token_path = os.getenv("BENJAMIN_GOOGLE_TOKEN_PATH", str(Path(state_dir) / "google_token.json"))
    try:
        from benjamin.core.integrations.google_calendar import GoogleCalendarConnector
        from benjamin.core.integrations.google_gmail import GoogleGmailConnector

        return GoogleCalendarConnector(token_path=token_path), GoogleGmailConnector(token_path=token_path)
    except Exception:
        return None, None

def run_reminder(
    message: str,
    state_dir: str,
    job_id: str | None = None,
    router: NotificationRouter | None = None,
) -> None:
    correlation_id = str(uuid4())
    active_router = router or build_notification_router()
    notify_meta = {"correlation_id": correlation_id}
    if job_id:
        notify_meta["job_id"] = job_id
    active_router.send(title="Reminder", body=message, meta=notify_meta)

    memory = _memory_manager_for_state(state_dir)
    memory.episodic.append(
        kind="notification",
        summary=f"Sent reminder: {message}",
        meta=notify_meta,
    )


def run_daily_briefing(
    state_dir: str,
    job_id: str | None = None,
    router: NotificationRouter | None = None,
    calendar_connector: CalendarConnector | None = None,
    email_connector: EmailConnector | None = None,
) -> None:
    memory = _memory_manager_for_state(state_dir)
    if calendar_connector is None and email_connector is None:
        calendar_connector, email_connector = _build_default_connectors(state_dir)
    recent_events = memory.episodic.list_recent(limit=3)
    preferences = [
        fact for fact in memory.semantic.list_all(scope="global") if fact.key.startswith("preference:")
    ][:5]

    timezone = ZoneInfo(os.getenv("BENJAMIN_TIMEZONE", "America/New_York"))
    now = datetime.now(timezone)

    sections: list[str] = []

    if calendar_connector is not None:
        schedule = calendar_connector.search_events(
            calendar_id=os.getenv("BENJAMIN_CALENDAR_ID", "primary"),
            time_min_iso=now.isoformat(),
            time_max_iso=(now + timedelta(hours=12)).isoformat(),
            query=None,
            max_results=5,
        )
        if schedule:
            sections.extend(["Today's schedule:"])
            for event in schedule[:5]:
                sections.append(f"- {event.get('start_iso')} | {event.get('title', '(untitled)')}")
            sections.append("")

    if email_connector is not None:
        query = os.getenv(
            "BENJAMIN_GMAIL_QUERY_IMPORTANT",
            "newer_than:1d -category:social -category:promotions",
        )
        messages = email_connector.search_messages(query=query, max_results=5)
        if messages:
            sections.extend(["Important emails:"])
            for msg in messages[:5]:
                summary = email_connector.thread_summary(msg.get("thread_id", ""), max_messages=3)
                snippets = summary.get("snippets", [])
                snippet = snippets[0] if snippets else msg.get("snippet", "")
                sections.append(f"- {msg.get('subject', '(no subject)')} — {snippet}")
            sections.append("")

    event_lines = [f"- {event.summary}" for event in recent_events] or ["- No recent events"]
    preference_lines = [f"- {fact.key}: {fact.value}" for fact in preferences] or ["- No saved preferences"]
    sections.extend(
        [
            "Recent episodes:",
            *event_lines,
            "",
            "Top preferences:",
            *preference_lines,
        ]
    )
    body = "\n".join(sections)

    correlation_id = str(uuid4())
    active_router = router or build_notification_router()
    notify_meta = {"correlation_id": correlation_id}
    if job_id:
        notify_meta["job_id"] = job_id
    active_router.send(title="Daily Briefing", body=body, meta=notify_meta)

    memory.episodic.append(
        kind="briefing",
        summary="Sent daily briefing",
        meta={
            "job_id": job_id,
            "correlation_id": correlation_id,
            "items": {
                "recent_events": [event.summary for event in recent_events],
                "preferences": [f"{fact.key}:{fact.value}" for fact in preferences],
            },
            "calendar_included": calendar_connector is not None,
            "gmail_included": email_connector is not None,
        },
    )
