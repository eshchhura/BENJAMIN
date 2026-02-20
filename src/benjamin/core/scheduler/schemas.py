from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class JobInfo(BaseModel):
    id: str
    next_run_time_iso: str | None
    trigger: str
    kwargs: dict = Field(default_factory=dict)


class ReminderRequest(BaseModel):
    message: str
    run_at_iso: str


class DailyBriefingRequest(BaseModel):
    time_hhmm: str

    @field_validator("time_hhmm")
    @classmethod
    def validate_time_hhmm(cls, value: str) -> str:
        parts = value.split(":")
        if len(parts) != 2:
            raise ValueError("time_hhmm must be HH:MM")
        hour_text, minute_text = parts
        if not (hour_text.isdigit() and minute_text.isdigit()):
            raise ValueError("time_hhmm must be HH:MM")
        hour = int(hour_text)
        minute = int(minute_text)
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError("time_hhmm must be HH:MM in 24h format")
        return f"{hour:02d}:{minute:02d}"
