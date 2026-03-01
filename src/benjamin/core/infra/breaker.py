from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


_BREAKER_STATES = {"closed", "open", "half_open"}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


@dataclass
class CircuitBreaker:
    service: str
    failure_threshold: int = 3
    open_seconds: int = 60
    half_open_max_trials: int = 1
    state: str = "closed"
    failure_count: int = 0
    opened_at: datetime | None = None
    last_failure: datetime | None = None
    last_error: str | None = None
    half_open_trials_used: int = 0

    def __post_init__(self) -> None:
        if self.state not in _BREAKER_STATES:
            self.state = "closed"

    def allow_request(self, now: datetime | None = None) -> bool:
        current = now or _utc_now()
        if self.state == "closed":
            return True
        if self.state == "open":
            if self.opened_at is not None and current >= self.opened_at + timedelta(seconds=max(1, self.open_seconds)):
                self.state = "half_open"
                self.half_open_trials_used = 0
            else:
                return False
        if self.state == "half_open":
            if self.half_open_trials_used >= max(1, self.half_open_max_trials):
                return False
            self.half_open_trials_used += 1
            return True
        return True

    def record_success(self, now: datetime | None = None) -> tuple[str, str] | None:
        previous = self.state
        self.failure_count = 0
        self.last_error = None
        self.last_failure = None
        self.half_open_trials_used = 0
        self.state = "closed"
        self.opened_at = None
        if previous != self.state:
            return previous, self.state
        return None

    def record_failure(self, error_str: str, now: datetime | None = None) -> tuple[str, str] | None:
        current = now or _utc_now()
        self.last_error = error_str
        self.last_failure = current
        previous = self.state

        if self.state == "half_open":
            self.state = "open"
            self.opened_at = current
            self.failure_count = max(self.failure_threshold, self.failure_count + 1)
            self.half_open_trials_used = 0
            return (previous, self.state) if previous != self.state else None

        self.failure_count += 1
        if self.failure_count >= max(1, self.failure_threshold):
            self.state = "open"
            self.opened_at = current
            self.half_open_trials_used = 0

        if previous != self.state:
            return previous, self.state
        return None

    def to_dict(self) -> dict[str, object]:
        return {
            "state": self.state,
            "failure_count": self.failure_count,
            "opened_at_iso": _to_iso(self.opened_at),
            "last_failure_iso": _to_iso(self.last_failure),
            "last_error": self.last_error,
            "half_open_trials_used": self.half_open_trials_used,
        }

    @classmethod
    def from_dict(
        cls,
        service: str,
        payload: dict[str, object],
        *,
        failure_threshold: int,
        open_seconds: int,
        half_open_max_trials: int,
    ) -> "CircuitBreaker":
        return cls(
            service=service,
            failure_threshold=failure_threshold,
            open_seconds=open_seconds,
            half_open_max_trials=half_open_max_trials,
            state=str(payload.get("state") or "closed"),
            failure_count=int(payload.get("failure_count") or 0),
            opened_at=_parse_iso(payload.get("opened_at_iso") if isinstance(payload.get("opened_at_iso"), str) else None),
            last_failure=_parse_iso(payload.get("last_failure_iso") if isinstance(payload.get("last_failure_iso"), str) else None),
            last_error=str(payload.get("last_error")) if payload.get("last_error") is not None else None,
            half_open_trials_used=int(payload.get("half_open_trials_used") or 0),
        )
