from __future__ import annotations

import os
import signal
import time
from pathlib import Path

from benjamin.core.infra.breaker_manager import BreakerManager
from benjamin.core.memory.manager import MemoryManager
from benjamin.core.notifications.notifier import build_notification_router
from benjamin.core.ops.maintenance import run_doctor_validate, run_weekly_compact
from benjamin.core.ops.safe_mode import is_safe_mode_enabled
from benjamin.core.scheduler.scheduler import SchedulerService


class Worker:
    def __init__(self) -> None:
        self.memory_manager = MemoryManager()
        self.scheduler = SchedulerService(state_dir=self.memory_manager.state_dir)
        self.notification_router = build_notification_router()
        self.breaker_manager = BreakerManager(state_dir=self.memory_manager.state_dir, memory_manager=self.memory_manager)
        self._running = True

    def _maintenance_enabled(self) -> bool:
        return os.getenv("BENJAMIN_MAINTENANCE_ENABLED", "on").strip().casefold() == "on"

    def _parse_hhmm(self, value: str, default: tuple[int, int]) -> tuple[int, int]:
        try:
            hour_raw, minute_raw = value.split(":", 1)
            hour = int(hour_raw)
            minute = int(minute_raw)
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                return hour, minute
        except Exception:
            pass
        return default

    def _schedule_maintenance_jobs(self) -> None:
        if not self._maintenance_enabled():
            return
        doctor_hour, doctor_minute = self._parse_hhmm(os.getenv("BENJAMIN_DOCTOR_VALIDATE_TIME", "09:10"), (9, 10))
        compact_hour, compact_minute = self._parse_hhmm(os.getenv("BENJAMIN_WEEKLY_COMPACT_TIME", "03:30"), (3, 30))
        compact_dow = os.getenv("BENJAMIN_WEEKLY_COMPACT_DOW", "sun").strip().casefold() or "sun"

        self.scheduler.scheduler.add_job(
            run_doctor_validate,
            trigger="cron",
            id="maintenance:doctor_validate",
            hour=doctor_hour,
            minute=doctor_minute,
            timezone=self.scheduler.timezone,
            kwargs={
                "state_dir": self.memory_manager.state_dir,
                "notifier": self.notification_router,
                "memory_manager": self.memory_manager,
                "breaker_manager": self.breaker_manager,
                "safe_mode_snapshot": is_safe_mode_enabled(Path(self.memory_manager.state_dir)),
            },
            replace_existing=True,
        )

        self.scheduler.scheduler.add_job(
            run_weekly_compact,
            trigger="cron",
            id="maintenance:weekly_compact",
            day_of_week=compact_dow,
            hour=compact_hour,
            minute=compact_minute,
            timezone=self.scheduler.timezone,
            kwargs={
                "state_dir": self.memory_manager.state_dir,
                "notifier": self.notification_router,
                "memory_manager": self.memory_manager,
            },
            replace_existing=True,
        )

    def _handle_signal(self, signum, frame) -> None:  # type: ignore[no-untyped-def]
        _ = frame
        print(f"[worker] received signal {signum}; shutting down")
        self._running = False

    def run_forever(self) -> None:
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)
        self._schedule_maintenance_jobs()
        self.scheduler.start()
        print("[worker] scheduler started")
        try:
            while self._running:
                time.sleep(0.5)
        finally:
            self.scheduler.shutdown()
            print("[worker] scheduler stopped")


def run() -> None:
    Worker().run_forever()


if __name__ == "__main__":
    run()
