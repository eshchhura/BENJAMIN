from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from benjamin.core.ops.safe_mode import is_safe_mode_enabled, safe_mode_env_forced, set_safe_mode_enabled

router = APIRouter()


@router.get("/safe-mode")
def get_safe_mode(request: Request) -> dict[str, bool]:
    return {"enabled": is_safe_mode_enabled(request.app.state.memory_manager.state_dir)}


@router.post("/safe-mode/enable")
def enable_safe_mode(request: Request) -> dict[str, bool]:
    set_safe_mode_enabled(request.app.state.memory_manager.state_dir, True)
    return {"enabled": True}


@router.post("/safe-mode/disable")
def disable_safe_mode(request: Request) -> dict[str, bool]:
    if safe_mode_env_forced():
        raise HTTPException(status_code=409, detail="Safe mode forced by env")
    set_safe_mode_enabled(request.app.state.memory_manager.state_dir, False)
    return {"enabled": False}
