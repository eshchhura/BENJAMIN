from __future__ import annotations

import json
from datetime import datetime
from uuid import uuid4

from benjamin.core.scheduler.jobs import run_reminder
from benjamin.core.scheduler.scheduler import SchedulerService
from benjamin.core.skills.base import SkillResult


class RemindersCreateSkill:
    name = "reminders.create"
    side_effect = "write"

    def __init__(self, scheduler: SchedulerService, state_dir: str) -> None:
        self.scheduler = scheduler
        self.state_dir = state_dir

    def run(self, query: str) -> SkillResult:
        payload = json.loads(query)
        message = payload["message"]
        run_at = datetime.fromisoformat(payload["run_at_iso"])
        job_id = f"reminder:{uuid4()}"
        self.scheduler.add_one_off(
            job_id=job_id,
            run_at_dt=run_at,
            func=run_reminder,
            kwargs={"message": message, "state_dir": self.state_dir, "job_id": job_id, "scheduled_run_iso": run_at.isoformat()},
        )
        return SkillResult(content=json.dumps({"job_id": job_id, "scheduled_for_iso": run_at.isoformat()}))


class RemindersSkill:
    name = "reminders"

    def run(self, query: str) -> SkillResult:
        return SkillResult(content=f"Reminder created: {query}")
