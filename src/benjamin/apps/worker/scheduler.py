from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class ScheduledTask:
    name: str
    run_at: datetime


class Scheduler:
    def schedule_in_minutes(self, name: str, minutes: int) -> ScheduledTask:
        return ScheduledTask(name=name, run_at=datetime.utcnow() + timedelta(minutes=minutes))
