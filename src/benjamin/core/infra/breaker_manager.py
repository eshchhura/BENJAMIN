from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, TypeVar

from benjamin.core.memory.manager import MemoryManager

from .breaker import CircuitBreaker
from .breaker_store import BreakerStore

SERVICES = ("llm", "gmail", "calendar")
T = TypeVar("T")


class ServiceDegradedError(RuntimeError):
    def __init__(self, service: str, last_error: str | None = None) -> None:
        self.service = service
        self.last_error = last_error
        suffix = f": {last_error}" if last_error else ""
        super().__init__(f"service_degraded:{service}{suffix}")


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


class BreakerManager:
    def __init__(self, state_dir: Path, memory_manager: MemoryManager | None = None) -> None:
        self.state_dir = state_dir
        self.enabled = os.getenv("BENJAMIN_BREAKERS_ENABLED", "on").casefold() != "off"
        self.failure_threshold = max(1, _env_int("BENJAMIN_BREAKER_FAILURE_THRESHOLD", 3))
        self.open_seconds = max(1, _env_int("BENJAMIN_BREAKER_OPEN_SECONDS", 60))
        self.half_open_max_trials = max(1, _env_int("BENJAMIN_BREAKER_HALFOPEN_MAX_TRIALS", 1))
        self.store = BreakerStore(state_dir)
        self.memory_manager = memory_manager or MemoryManager(state_dir=state_dir)
        loaded = self.store.load()
        self._breakers: dict[str, CircuitBreaker] = {}
        for service in SERVICES:
            payload = loaded.get(service, {})
            self._breakers[service] = CircuitBreaker.from_dict(
                service,
                payload,
                failure_threshold=self.failure_threshold,
                open_seconds=self.open_seconds,
                half_open_max_trials=self.half_open_max_trials,
            )

    def get(self, service: str) -> CircuitBreaker:
        if service not in self._breakers:
            self._breakers[service] = CircuitBreaker(
                service=service,
                failure_threshold=self.failure_threshold,
                open_seconds=self.open_seconds,
                half_open_max_trials=self.half_open_max_trials,
            )
        return self._breakers[service]

    def snapshot(self) -> dict[str, dict[str, object]]:
        return {name: breaker.to_dict() for name, breaker in self._breakers.items()}

    def wrap(self, service: str, fn: Callable[[], T]) -> T:
        if not self.enabled:
            return fn()

        breaker = self.get(service)
        previous_state = breaker.state
        if not breaker.allow_request():
            self._persist()
            self._record_transition_if_needed(service, previous_state, breaker.state, "cooldown elapsed")
            raise ServiceDegradedError(service, breaker.last_error)

        self._record_transition_if_needed(service, previous_state, breaker.state, "cooldown elapsed")
        self._persist()

        try:
            result = fn()
        except Exception as exc:
            before = breaker.state
            transition = breaker.record_failure(str(exc))
            self._persist()
            if transition is not None:
                self._record_transition(service, transition[0], transition[1], str(exc), correlation_id=self._current_correlation_id())
            elif before == breaker.state:
                self._record_increment(service, str(exc))
            raise

        transition = breaker.record_success()
        self._persist()
        if transition is not None:
            self._record_transition(service, transition[0], transition[1], "request succeeded", correlation_id=self._current_correlation_id())
        return result

    def _persist(self) -> None:
        self.store.save(self.snapshot())

    def _record_increment(self, service: str, reason: str) -> None:
        self.memory_manager.episodic.append(
            kind="infra",
            summary=f"Breaker failure recorded for {service}",
            meta={
                "service": service,
                "state": self.get(service).state,
                "reason": reason,
                "failure_count": self.get(service).failure_count,
                "ts_iso": datetime.now(timezone.utc).isoformat(),
                "correlation_id": self._current_correlation_id(),
            },
        )

    def _record_transition_if_needed(self, service: str, previous: str, current: str, reason: str) -> None:
        if previous != current:
            self._record_transition(service, previous, current, reason, correlation_id=self._current_correlation_id())

    def _record_transition(self, service: str, from_state: str, to_state: str, reason: str, correlation_id: str | None = None) -> None:
        self.memory_manager.episodic.append(
            kind="infra",
            summary=f"Circuit breaker {service} transitioned {from_state}->{to_state}",
            meta={
                "service": service,
                "from_state": from_state,
                "to_state": to_state,
                "reason": reason,
                "ts_iso": datetime.now(timezone.utc).isoformat(),
                "correlation_id": correlation_id,
            },
        )

    def _current_correlation_id(self) -> str | None:
        try:
            from benjamin.core.logging.context import get_log_context

            context = get_log_context()
            return str(context.get("correlation_id")) if context.get("correlation_id") else None
        except Exception:
            return None
