from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from pydantic import BaseModel

from benjamin.core.integrations.base import CalendarConnector
from benjamin.core.skills.base import SkillResult


class CalendarSearchInput(BaseModel):
    query: str | None = None
    days: int = 1
    hours_ahead: int = 12
    calendar_id: str | None = None
    max_results: int = 20


class CalendarSearchSkill:
    name = "calendar.search"
    side_effect = "read"

    def __init__(self, connector: CalendarConnector | None = None) -> None:
        self.connector = connector

    def run(self, query: str) -> SkillResult:
        payload = CalendarSearchInput.model_validate_json(query or "{}")
        if self.connector is None:
            return SkillResult(content=json.dumps({"events": [], "reason": "calendar_integration_unavailable"}))

        timezone = ZoneInfo(os.getenv("BENJAMIN_TIMEZONE", "America/New_York"))
        now = datetime.now(tz=timezone)
        if payload.hours_ahead > 0:
            window_end = now + timedelta(hours=payload.hours_ahead)
        else:
            window_end = now + timedelta(days=max(payload.days, 1))

        events = self.connector.search_events(
            calendar_id=payload.calendar_id or os.getenv("BENJAMIN_CALENDAR_ID", "primary"),
            time_min_iso=now.isoformat(),
            time_max_iso=window_end.isoformat(),
            query=payload.query,
            max_results=payload.max_results,
        )
        normalized = [
            {
                "title": event.get("title", ""),
                "start_iso": event.get("start_iso"),
                "end_iso": event.get("end_iso"),
                "location": event.get("location"),
            }
            for event in events
        ]
        return SkillResult(content=json.dumps({"events": normalized}))
