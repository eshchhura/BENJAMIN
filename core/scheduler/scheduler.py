from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler

from .schemas import JobInfo


class SchedulerService:
    def __init__(self, state_dir: Path | None = None) -> None:
        self.state_dir = state_dir or self._default_state_dir()
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.test_mode = os.getenv("BENJAMIN_TEST_MODE", "").casefold() in {"1", "true", "yes", "on"}
        self.timezone = ZoneInfo(os.getenv("BENJAMIN_TIMEZONE", "America/New_York"))
        self.scheduler = BackgroundScheduler(
            jobstores={"default": self._build_job_store()},
            timezone=self.timezone,
        )
        self._started = False

    def _default_state_dir(self) -> Path:
        configured = os.getenv("BENJAMIN_STATE_DIR")
        if configured:
            return Path(configured).expanduser()
        return Path.home() / ".benjamin"

    def _build_job_store(self):
        if self.test_mode:
            return MemoryJobStore()
        db_path = self.state_dir / "jobs.sqlite"
        return SQLAlchemyJobStore(url=f"sqlite:///{db_path}")

    def start(self) -> None:
        if self.test_mode or self._started:
            return
        self.scheduler.start()
        self._started = True

    def shutdown(self) -> None:
        if self._started:
            self.scheduler.shutdown(wait=False)
            self._started = False

    def list_jobs(self) -> list[JobInfo]:
        jobs: list[JobInfo] = []
        for job in self.scheduler.get_jobs():
            try:
                next_run_time = job.next_run_time
            except AttributeError:
                next_run_time = None
            jobs.append(
                JobInfo(
                    id=job.id,
                    next_run_time_iso=next_run_time.isoformat() if next_run_time else None,
                    trigger=str(job.trigger),
                    kwargs=job.kwargs,
                )
            )
        return jobs

    def add_one_off(self, job_id: str, run_at_dt: datetime, func: Callable[..., Any], kwargs: dict[str, Any]) -> None:
        self.scheduler.add_job(
            func,
            trigger="date",
            id=job_id,
            run_date=run_at_dt,
            kwargs=kwargs,
            replace_existing=True,
        )

    def add_cron(
        self,
        job_id: str,
        hour: int,
        minute: int,
        timezone: ZoneInfo,
        func: Callable[..., Any],
        kwargs: dict[str, Any],
    ) -> None:
        self.scheduler.add_job(
            func,
            trigger="cron",
            id=job_id,
            hour=hour,
            minute=minute,
            timezone=timezone,
            kwargs=kwargs,
            replace_existing=True,
        )

    def remove_job(self, job_id: str) -> None:
        self.scheduler.remove_job(job_id)
