from __future__ import annotations

READ_SCOPES: tuple[str, ...] = (
    "filesystem.read",
    "web.read",
    "calendar.read",
    "gmail.read",
    "memory.read",
    "rules.read",
    "jobs.read",
)

WRITE_SCOPES: tuple[str, ...] = (
    "reminders.write",
    "calendar.write",
    "gmail.draft",
    "gmail.send",
    "memory.write",
    "rules.write",
    "jobs.write",
)

ALL_SCOPES: tuple[str, ...] = READ_SCOPES + WRITE_SCOPES


SKILL_SCOPE_DEFAULTS: dict[str, list[str]] = {
    "filesystem": ["filesystem.read"],
    "filesystem.search_read": ["filesystem.read"],
    "web.search": ["web.read"],
    "web_search": ["web.read"],
    "calendar.search": ["calendar.read"],
    "calendar.create_event": ["calendar.write"],
    "gmail.search": ["gmail.read"],
    "gmail.read_message": ["gmail.read"],
    "gmail.thread_summary": ["gmail.read"],
    "gmail.draft_email": ["gmail.draft"],
    "reminders.create": ["reminders.write"],
}


def default_scopes_for_skill(skill_name: str, side_effect: str | None = None) -> list[str]:
    if skill_name in SKILL_SCOPE_DEFAULTS:
        return list(SKILL_SCOPE_DEFAULTS[skill_name])

    normalized_effect = (side_effect or "read").casefold()
    if normalized_effect == "write":
        return ["jobs.write"]
    return ["jobs.read"]
