from __future__ import annotations

from datetime import datetime
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException

from benjamin.core.memory.manager import MemoryManager
from benjamin.core.scheduler.jobs import run_daily_briefing, run_reminder
from benjamin.core.scheduler.scheduler import SchedulerService
from benjamin.core.scheduler.schemas import DailyBriefingRequest, JobInfo, ReminderRequest

from .deps import get_memory_manager, get_scheduler_service

router = APIRouter()


@router.get("", response_model=list[JobInfo])
def list_jobs(scheduler: SchedulerService = Depends(get_scheduler_service)) -> list[JobInfo]:
    return scheduler.list_jobs()


@router.post("/reminder")
def create_reminder(
    request: ReminderRequest,
    scheduler: SchedulerService = Depends(get_scheduler_service),
    memory_manager: MemoryManager = Depends(get_memory_manager),
) -> dict[str, str]:
    try:
        run_at = datetime.fromisoformat(request.run_at_iso)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="run_at_iso must be an ISO datetime") from exc

    job_id = f"reminder:{uuid4()}"
    scheduler.add_one_off(
        job_id=job_id,
        run_at_dt=run_at,
        func=run_reminder,
        kwargs={
            "message": request.message,
            "state_dir": str(memory_manager.state_dir),
            "job_id": job_id,
            "scheduled_run_iso": run_at.isoformat(),
        },
    )
    return {"job_id": job_id, "scheduled_for_iso": run_at.isoformat()}


@router.post("/daily-briefing")
def upsert_daily_briefing(
    request: DailyBriefingRequest,
    scheduler: SchedulerService = Depends(get_scheduler_service),
    memory_manager: MemoryManager = Depends(get_memory_manager),
) -> dict[str, str]:
    hour, minute = [int(part) for part in request.time_hhmm.split(":")]
    timezone = scheduler.timezone
    scheduler.add_cron(
        job_id="daily-briefing",
        hour=hour,
        minute=minute,
        timezone=timezone,
        func=run_daily_briefing,
        kwargs={"state_dir": str(memory_manager.state_dir), "job_id": "daily-briefing"},
    )
    return {"job_id": "daily-briefing", "time_hhmm": request.time_hhmm}


@router.delete("/{job_id}")
def delete_job(job_id: str, scheduler: SchedulerService = Depends(get_scheduler_service)) -> dict[str, str]:
    try:
        scheduler.remove_job(job_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"job not found: {job_id}") from exc
    return {"status": "deleted", "job_id": job_id}
