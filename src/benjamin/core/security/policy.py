from __future__ import annotations

import os

from benjamin.core.security.scopes import ALL_SCOPES, READ_SCOPES


class PermissionsPolicy:
    def __init__(
        self,
        *,
        scope_mode: str | None = None,
        scopes_enabled_raw: str | None = None,
        rules_allowed_raw: str | None = None,
    ) -> None:
        self.scope_mode = (scope_mode or os.getenv("BENJAMIN_SCOPE_MODE", "default")).strip().casefold() or "default"
        if self.scope_mode not in {"default", "allowlist"}:
            self.scope_mode = "default"

        raw_scopes = scopes_enabled_raw if scopes_enabled_raw is not None else os.getenv("BENJAMIN_SCOPES_ENABLED", "")
        self.explicit_scopes_enabled = self._parse_csv(raw_scopes)

        raw_rules = rules_allowed_raw if rules_allowed_raw is not None else os.getenv("BENJAMIN_RULES_ALLOWED_SCOPES", "")
        if raw_rules.strip() == "":
            self.rules_allowed_scopes = {"reminders.write"}
        else:
            self.rules_allowed_scopes = self._parse_csv(raw_rules)

    @staticmethod
    def _parse_csv(raw: str) -> set[str]:
        return {item.strip() for item in raw.split(",") if item.strip()}

    def is_scope_enabled(self, scope: str) -> bool:
        if self.scope_mode == "allowlist":
            return scope in self.explicit_scopes_enabled
        # default mode: all read scopes enabled + explicit allowlist for writes/others.
        return scope in READ_SCOPES or scope in self.explicit_scopes_enabled

    def check_scopes(self, scopes: list[str]) -> tuple[bool, list[str]]:
        disabled = sorted({scope for scope in scopes if not self.is_scope_enabled(scope)})
        return len(disabled) == 0, disabled

    def can_rules_propose(self, scopes: list[str]) -> bool:
        return all(scope in self.rules_allowed_scopes for scope in scopes)

    def snapshot(self) -> dict[str, list[str]]:
        enabled_scopes = [scope for scope in ALL_SCOPES if self.is_scope_enabled(scope)]
        return {
            "enabled_scopes": enabled_scopes,
            "rules_allowed_scopes": sorted(self.rules_allowed_scopes),
        }
