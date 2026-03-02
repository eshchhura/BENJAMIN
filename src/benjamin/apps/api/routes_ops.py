from __future__ import annotations

from fastapi import APIRouter, Request

from benjamin.core.ops.doctor import run_doctor

router = APIRouter()


@router.get("/doctor")
def get_doctor_report(request: Request) -> dict:
    report = run_doctor(state_dir=request.app.state.memory_manager.state_dir)
    return report.model_dump()
