from __future__ import annotations

from benjamin.core.integrations.google_auth import build_google_service


class GoogleCalendarConnector:
    def __init__(self, token_path: str) -> None:
        self.service = build_google_service("calendar", "v3", token_path)

    def search_events(
        self,
        calendar_id: str,
        time_min_iso: str,
        time_max_iso: str,
        query: str | None,
        max_results: int,
    ) -> list[dict]:
        response = (
            self.service.events()
            .list(
                calendarId=calendar_id,
                q=query,
                timeMin=time_min_iso,
                timeMax=time_max_iso,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = []
        for item in response.get("items", []):
            start = item.get("start", {})
            end = item.get("end", {})
            events.append(
                {
                    "id": item.get("id"),
                    "title": item.get("summary", "(untitled)"),
                    "start_iso": start.get("dateTime") or start.get("date"),
                    "end_iso": end.get("dateTime") or end.get("date"),
                    "location": item.get("location"),
                    "attendees_count": len(item.get("attendees", [])),
                }
            )
        return events
