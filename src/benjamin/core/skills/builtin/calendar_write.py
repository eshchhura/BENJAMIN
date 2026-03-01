from __future__ import annotations

import json
import os

from pydantic import BaseModel, Field

from benjamin.core.infra.breaker_manager import ServiceDegradedError
from benjamin.core.integrations.base import CalendarConnector
from benjamin.core.skills.base import SkillResult


class CalendarCreateEventInput(BaseModel):
    title: str
    start_iso: str
    end_iso: str
    timezone: str | None = None
    location: str | None = None
    description: str | None = None
    attendees: list[str] = Field(default_factory=list)
    calendar_id: str | None = None


class CalendarCreateEventSkill:
    name = "calendar.create_event"
    side_effect = "write"

    def __init__(self, connector: CalendarConnector | None = None) -> None:
        self.connector = connector

    def run(self, query: str) -> SkillResult:
        payload = CalendarCreateEventInput.model_validate_json(query)
        if self.connector is None:
            raise RuntimeError("calendar_integration_unavailable")

        timezone = payload.timezone or os.getenv("BENJAMIN_TIMEZONE", "America/New_York")
        calendar_id = payload.calendar_id or os.getenv("BENJAMIN_CALENDAR_ID", "primary")
        try:
            created = self.connector.create_event(
                calendar_id=calendar_id,
                title=payload.title,
                start_iso=payload.start_iso,
                end_iso=payload.end_iso,
                timezone=timezone,
                location=payload.location,
                description=payload.description,
                attendees=payload.attendees,
            )
        except ServiceDegradedError:
            return SkillResult(content=json.dumps({"reason": "service_degraded:calendar"}))
        return SkillResult(
            content=json.dumps(
                {
                    "event_id": created.get("id", ""),
                    "html_link": created.get("html_link"),
                    "title": created.get("title", payload.title),
                    "start_iso": created.get("start_iso", payload.start_iso),
                    "end_iso": created.get("end_iso", payload.end_iso),
                }
            )
        )
