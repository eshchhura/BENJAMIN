from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Iterator

correlation_id_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)
task_id_var: ContextVar[str | None] = ContextVar("task_id", default=None)
approval_id_var: ContextVar[str | None] = ContextVar("approval_id", default=None)
rule_id_var: ContextVar[str | None] = ContextVar("rule_id", default=None)
job_id_var: ContextVar[str | None] = ContextVar("job_id", default=None)

_CONTEXT_VARS: dict[str, ContextVar[str | None]] = {
    "correlation_id": correlation_id_var,
    "task_id": task_id_var,
    "approval_id": approval_id_var,
    "rule_id": rule_id_var,
    "job_id": job_id_var,
}


def set_context(**kwargs: str | None) -> dict[str, Token[str | None]]:
    tokens: dict[str, Token[str | None]] = {}
    for key, value in kwargs.items():
        var = _CONTEXT_VARS.get(key)
        if var is None:
            continue
        tokens[key] = var.set(value)
    return tokens


def reset_context(tokens: dict[str, Token[str | None]]) -> None:
    for key, token in tokens.items():
        var = _CONTEXT_VARS.get(key)
        if var is not None:
            var.reset(token)


@contextmanager
def log_context(
    correlation_id: str | None = None,
    task_id: str | None = None,
    approval_id: str | None = None,
    rule_id: str | None = None,
    job_id: str | None = None,
) -> Iterator[None]:
    tokens = set_context(
        correlation_id=correlation_id,
        task_id=task_id,
        approval_id=approval_id,
        rule_id=rule_id,
        job_id=job_id,
    )
    try:
        yield
    finally:
        reset_context(tokens)


def get_log_context() -> dict[str, str]:
    values = {
        "correlation_id": correlation_id_var.get(),
        "task_id": task_id_var.get(),
        "approval_id": approval_id_var.get(),
        "rule_id": rule_id_var.get(),
        "job_id": job_id_var.get(),
    }
    return {key: value for key, value in values.items() if value is not None}
