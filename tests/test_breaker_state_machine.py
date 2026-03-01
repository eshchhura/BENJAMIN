from datetime import datetime, timedelta, timezone

from benjamin.core.infra.breaker import CircuitBreaker


def test_breaker_transitions() -> None:
    now = datetime(2025, 1, 1, tzinfo=timezone.utc)
    breaker = CircuitBreaker(service="llm", failure_threshold=3, open_seconds=60, half_open_max_trials=1)

    assert breaker.allow_request(now=now) is True
    assert breaker.record_failure("e1", now=now) is None
    assert breaker.state == "closed"

    assert breaker.record_failure("e2", now=now + timedelta(seconds=1)) is None
    transition = breaker.record_failure("e3", now=now + timedelta(seconds=2))
    assert transition == ("closed", "open")
    assert breaker.state == "open"

    assert breaker.allow_request(now=now + timedelta(seconds=10)) is False
    assert breaker.allow_request(now=now + timedelta(seconds=63)) is True
    assert breaker.state == "half_open"
    assert breaker.allow_request(now=now + timedelta(seconds=62)) is False

    closed_transition = breaker.record_success(now=now + timedelta(seconds=63))
    assert closed_transition == ("half_open", "closed")
    assert breaker.state == "closed"

    breaker.record_failure("e1", now=now + timedelta(seconds=64))
    breaker.record_failure("e2", now=now + timedelta(seconds=65))
    breaker.record_failure("e3", now=now + timedelta(seconds=66))
    assert breaker.state == "open"
    assert breaker.allow_request(now=now + timedelta(seconds=131)) is True
    reopen = breaker.record_failure("still broken", now=now + timedelta(seconds=132))
    assert reopen == ("half_open", "open")
