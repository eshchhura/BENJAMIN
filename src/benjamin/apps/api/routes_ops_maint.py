from __future__ import annotations

from fastapi import APIRouter, Request

from benjamin.core.ops.maintenance import (
    load_maintenance_status,
    run_doctor_validate,
    run_weekly_compact,
)
from benjamin.core.ops.safe_mode import is_safe_mode_enabled

router = APIRouter()


@router.get("/maintenance")
def get_maintenance_status(request: Request) -> dict:
    return load_maintenance_status(request.app.state.memory_manager.state_dir)


@router.post("/maintenance/run-doctor-now")
def run_doctor_now(request: Request) -> dict:
    report = run_doctor_validate(
        state_dir=request.app.state.memory_manager.state_dir,
        notifier=request.app.state.notification_router,
        memory_manager=request.app.state.memory_manager,
        breaker_manager=request.app.state.breaker_manager,
        safe_mode_snapshot=is_safe_mode_enabled(request.app.state.memory_manager.state_dir),
    )
    return report.model_dump()


@router.post("/maintenance/run-compact-now")
def run_compact_now(request: Request) -> dict:
    return run_weekly_compact(
        state_dir=request.app.state.memory_manager.state_dir,
        notifier=request.app.state.notification_router,
        memory_manager=request.app.state.memory_manager,
    )
