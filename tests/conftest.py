from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def disable_auth_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BENJAMIN_AUTH_MODE", "off")
    monkeypatch.delenv("BENJAMIN_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("BENJAMIN_EXPOSE_PUBLIC", raising=False)
