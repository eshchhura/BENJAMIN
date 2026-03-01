from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def disable_auth_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BENJAMIN_AUTH_MODE", "off")
    monkeypatch.delenv("BENJAMIN_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("BENJAMIN_EXPOSE_PUBLIC", raising=False)


@pytest.fixture(autouse=True)
def enable_common_write_scopes_for_legacy_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "BENJAMIN_SCOPES_ENABLED",
        "reminders.write,calendar.write,gmail.draft,memory.write,rules.write,jobs.write",
    )
    monkeypatch.setenv("BENJAMIN_SCOPE_MODE", "default")
    monkeypatch.setenv("BENJAMIN_RULES_ALLOWED_SCOPES", "reminders.write,calendar.write,gmail.draft,jobs.write")
