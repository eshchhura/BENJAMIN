from __future__ import annotations

import signal
import time

from benjamin.core.scheduler.scheduler import SchedulerService


class Worker:
    def __init__(self) -> None:
        self.scheduler = SchedulerService()
        self._running = True

    def _handle_signal(self, signum, frame) -> None:  # type: ignore[no-untyped-def]
        _ = frame
        print(f"[worker] received signal {signum}; shutting down")
        self._running = False

    def run_forever(self) -> None:
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)
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
