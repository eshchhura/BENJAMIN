from __future__ import annotations

from typing import Protocol


class CalendarConnector(Protocol):
    def search_events(
        self,
        calendar_id: str,
        time_min_iso: str,
        time_max_iso: str,
        query: str | None,
        max_results: int,
    ) -> list[dict]: ...

    def create_event(
        self,
        calendar_id: str,
        title: str,
        start_iso: str,
        end_iso: str,
        timezone: str,
        location: str | None,
        description: str | None,
        attendees: list[str] | None,
    ) -> dict: ...


class EmailConnector(Protocol):
    def search_messages(self, query: str, max_results: int) -> list[dict]: ...

    def read_message(self, message_id: str) -> dict: ...

    def thread_summary(self, thread_id: str, max_messages: int = 10) -> dict: ...

    def create_draft(
        self,
        to: list[str],
        cc: list[str] | None,
        bcc: list[str] | None,
        subject: str,
        body: str,
    ) -> dict: ...
