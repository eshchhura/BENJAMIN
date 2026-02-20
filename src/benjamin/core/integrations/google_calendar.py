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
    ) -> dict:
        body = {
            "summary": title,
            "start": {"dateTime": start_iso, "timeZone": timezone},
            "end": {"dateTime": end_iso, "timeZone": timezone},
        }
        if location:
            body["location"] = location
        if description:
            body["description"] = description
        if attendees:
            body["attendees"] = [{"email": email} for email in attendees]

        try:
            response = (
                self.service.events()
                .insert(calendarId=calendar_id, body=body, fields="id,summary,start,end,htmlLink")
                .execute()
            )
        except Exception as exc:  # pragma: no cover - depends on external client exception class
            raise RuntimeError(f"google_calendar_create_event_failed: {exc}") from exc

        start = response.get("start", {})
        end = response.get("end", {})
        return {
            "id": response.get("id"),
            "title": response.get("summary", title),
            "start_iso": start.get("dateTime") or start_iso,
            "end_iso": end.get("dateTime") or end_iso,
            "html_link": response.get("htmlLink"),
        }
