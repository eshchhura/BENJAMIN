import json

from benjamin.core.skills.builtin.calendar_read import CalendarSearchSkill


class MockCalendarConnector:
    def search_events(self, calendar_id: str, time_min_iso: str, time_max_iso: str, query: str | None, max_results: int) -> list[dict]:
        assert calendar_id
        assert max_results == 2
        return [
            {
                "id": "evt-1",
                "title": "Design Review",
                "start_iso": "2026-02-21T09:00:00-05:00",
                "end_iso": "2026-02-21T10:00:00-05:00",
                "location": "Room A",
                "attendees_count": 3,
            }
        ]


def test_calendar_search_skill_returns_mocked_events() -> None:
    skill = CalendarSearchSkill(connector=MockCalendarConnector())
    result = skill.run(json.dumps({"query": "design", "hours_ahead": 4, "max_results": 2}))

    payload = json.loads(result.content)
    assert payload["events"][0]["title"] == "Design Review"
    assert payload["events"][0]["location"] == "Room A"
