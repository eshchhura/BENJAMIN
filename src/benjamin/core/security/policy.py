from __future__ import annotations

import os
from pydantic import BaseModel, Field

from benjamin.core.security.overrides import PolicyOverridesStore
from benjamin.core.security.scopes import ALL_SCOPES, READ_SCOPES


class PolicySnapshot(BaseModel):
    mode: str
    scopes_enabled: list[str] = Field(default_factory=list)
    rules_allowed_scopes: list[str] = Field(default_factory=list)
    overrides_enabled: bool


class PermissionsPolicy:
    DEFAULT_RULES_ALLOWED_SCOPES = {"reminders.write"}

    def __init__(
        self,
        *,
        scope_mode: str | None = None,
        scopes_enabled_raw: str | None = None,
        rules_allowed_raw: str | None = None,
        overrides_store: PolicyOverridesStore | None = None,
    ) -> None:
        self.scope_mode = (scope_mode or os.getenv("BENJAMIN_SCOPE_MODE", "default")).strip().casefold() or "default"
        if self.scope_mode not in {"default", "allowlist"}:
            self.scope_mode = "default"

        raw_scopes = scopes_enabled_raw if scopes_enabled_raw is not None else os.getenv("BENJAMIN_SCOPES_ENABLED", "")
        self.explicit_scopes_enabled = self._parse_csv(raw_scopes)

        raw_rules = rules_allowed_raw if rules_allowed_raw is not None else os.getenv("BENJAMIN_RULES_ALLOWED_SCOPES", "")
        if raw_rules.strip() == "":
            self.rules_allowed_scopes = set(self.DEFAULT_RULES_ALLOWED_SCOPES)
        else:
            self.rules_allowed_scopes = self._parse_csv(raw_rules)

        self.overrides_enabled = os.getenv("BENJAMIN_POLICY_OVERRIDES", "on").strip().casefold() != "off"
        self.overrides_store = overrides_store or PolicyOverridesStore()
        if self.overrides_enabled:
            self._apply_overrides()

    @staticmethod
    def _parse_csv(raw: str) -> set[str]:
        return {item.strip() for item in raw.split(",") if item.strip()}

    def _apply_overrides(self) -> None:
        overrides = self.overrides_store.load()
        enabled_override = overrides.get("scopes_enabled")
        if isinstance(enabled_override, list):
            self.explicit_scopes_enabled = {scope for scope in enabled_override if isinstance(scope, str) and scope in ALL_SCOPES}

        rules_override = overrides.get("rules_allowed_scopes")
        if isinstance(rules_override, list):
            self.rules_allowed_scopes = {scope for scope in rules_override if isinstance(scope, str) and scope in ALL_SCOPES}

    def is_scope_enabled(self, scope: str) -> bool:
        if self.scope_mode == "allowlist":
            return scope in self.explicit_scopes_enabled
        return scope in READ_SCOPES or scope in self.explicit_scopes_enabled

    def check_scopes(self, scopes: list[str]) -> tuple[bool, list[str]]:
        disabled = sorted({scope for scope in scopes if not self.is_scope_enabled(scope)})
        return len(disabled) == 0, disabled

    def check_rules_allowlist(self, scopes: list[str]) -> tuple[bool, list[str]]:
        blocked = sorted({scope for scope in scopes if scope not in self.rules_allowed_scopes})
        return len(blocked) == 0, blocked

    def can_rules_propose(self, scopes: list[str]) -> bool:
        return self.check_rules_allowlist(scopes)[0]

    def snapshot_model(self) -> PolicySnapshot:
        enabled_scopes = [scope for scope in ALL_SCOPES if self.is_scope_enabled(scope)]
        return PolicySnapshot(
            mode=self.scope_mode,
            scopes_enabled=enabled_scopes,
            rules_allowed_scopes=sorted(self.rules_allowed_scopes),
            overrides_enabled=self.overrides_enabled,
        )

    def snapshot(self) -> dict[str, list[str] | str | bool]:
        return self.snapshot_model().model_dump()
