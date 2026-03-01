from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from benjamin.core.security.overrides import PolicyOverridesStore
from benjamin.core.security.policy import PermissionsPolicy
from benjamin.core.security.scopes import ALL_SCOPES, READ_SCOPES, WRITE_SCOPES

router = APIRouter()


class ScopeListRequest(BaseModel):
    scopes: list[str] = Field(default_factory=list)


def _validate_scopes(scopes: list[str]) -> list[str]:
    unknown = sorted({scope for scope in scopes if scope not in ALL_SCOPES})
    if unknown:
        raise HTTPException(status_code=400, detail=f"unknown scopes: {','.join(unknown)}")
    return sorted({scope for scope in scopes})


def _guard_overrides_enabled(policy: PermissionsPolicy) -> None:
    if not policy.overrides_enabled:
        raise HTTPException(status_code=409, detail="policy overrides are disabled (env controlled)")


def _policy_payload(policy: PermissionsPolicy) -> dict:
    return {
        "policy": policy.snapshot(),
        "canonical_scopes": list(ALL_SCOPES),
        "scope_definitions": {"read": list(READ_SCOPES), "write": list(WRITE_SCOPES)},
    }


@router.get("/scopes")
def get_scopes(request: Request) -> dict:
    policy = PermissionsPolicy(overrides_store=PolicyOverridesStore(state_dir=request.app.state.memory_manager.state_dir))
    return _policy_payload(policy)


@router.post("/scopes/enable")
def enable_scopes(payload: ScopeListRequest, request: Request) -> dict:
    scopes = _validate_scopes(payload.scopes)
    store = PolicyOverridesStore(state_dir=request.app.state.memory_manager.state_dir)
    policy = PermissionsPolicy(overrides_store=store)
    _guard_overrides_enabled(policy)
    overrides = store.load()
    enabled = set(overrides.get("scopes_enabled", []))
    enabled.update(scopes)
    overrides["scopes_enabled"] = sorted(scope for scope in enabled if scope in ALL_SCOPES)
    overrides.setdefault("rules_allowed_scopes", policy.snapshot_model().rules_allowed_scopes)
    store.save(overrides)
    return _policy_payload(PermissionsPolicy(overrides_store=store))


@router.post("/scopes/disable")
def disable_scopes(payload: ScopeListRequest, request: Request) -> dict:
    scopes = _validate_scopes(payload.scopes)
    store = PolicyOverridesStore(state_dir=request.app.state.memory_manager.state_dir)
    policy = PermissionsPolicy(overrides_store=store)
    _guard_overrides_enabled(policy)
    current = set(store.load().get("scopes_enabled", policy.explicit_scopes_enabled))
    for scope in scopes:
        current.discard(scope)
    overrides = store.load()
    overrides["scopes_enabled"] = sorted(scope for scope in current if scope in ALL_SCOPES)
    overrides.setdefault("rules_allowed_scopes", policy.snapshot_model().rules_allowed_scopes)
    store.save(overrides)
    return _policy_payload(PermissionsPolicy(overrides_store=store))


@router.post("/rules/allowed-scopes")
def set_rules_allowed_scopes(payload: ScopeListRequest, request: Request) -> dict:
    scopes = _validate_scopes(payload.scopes)
    store = PolicyOverridesStore(state_dir=request.app.state.memory_manager.state_dir)
    policy = PermissionsPolicy(overrides_store=store)
    _guard_overrides_enabled(policy)
    overrides = store.load()
    overrides["rules_allowed_scopes"] = scopes
    overrides.setdefault("scopes_enabled", sorted(policy.explicit_scopes_enabled))
    store.save(overrides)
    return _policy_payload(PermissionsPolicy(overrides_store=store))


@router.post("/rules/allowed-scopes/reset")
def reset_rules_allowed_scopes(request: Request) -> dict:
    store = PolicyOverridesStore(state_dir=request.app.state.memory_manager.state_dir)
    policy = PermissionsPolicy(overrides_store=store)
    _guard_overrides_enabled(policy)
    overrides = store.load()
    overrides["rules_allowed_scopes"] = sorted(PermissionsPolicy.DEFAULT_RULES_ALLOWED_SCOPES)
    overrides.setdefault("scopes_enabled", sorted(policy.explicit_scopes_enabled))
    store.save(overrides)
    return _policy_payload(PermissionsPolicy(overrides_store=store))
