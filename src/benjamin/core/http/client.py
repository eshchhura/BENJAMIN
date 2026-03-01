from __future__ import annotations

import os
import random
import threading
import time

import httpx

from .errors import BenjaminHTTPNetworkError, BenjaminHTTPStatusError

_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_RETRYABLE_EXCEPTIONS = (httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError)
_DEFAULT_TIMEOUT_S = 15.0
_DEFAULT_CONNECT_TIMEOUT_S = 5.0
_DEFAULT_RETRIES = 2
_DEFAULT_BACKOFF_BASE_S = 0.25
_DEFAULT_BACKOFF_MAX_S = 2.0
_DEFAULT_USER_AGENT = "BENJAMIN/1.0"

_client: httpx.Client | None = None
_client_lock = threading.Lock()


def _get_float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _get_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _build_timeout(total_s: float | None = None) -> httpx.Timeout:
    connect_s = max(0.1, _get_float_env("BENJAMIN_HTTP_CONNECT_TIMEOUT_S", _DEFAULT_CONNECT_TIMEOUT_S))
    read_total = max(0.1, total_s if total_s is not None else _get_float_env("BENJAMIN_HTTP_TIMEOUT_S", _DEFAULT_TIMEOUT_S))
    return httpx.Timeout(read_total, connect=min(connect_s, read_total))


def get_http_client() -> httpx.Client:
    global _client
    if _client is not None:
        return _client

    with _client_lock:
        if _client is None:
            user_agent = os.getenv("BENJAMIN_HTTP_USER_AGENT", _DEFAULT_USER_AGENT)
            _client = httpx.Client(timeout=_build_timeout(), headers={"User-Agent": user_agent})
    return _client


def _safe_url(url: str, redact_url: bool) -> str:
    if redact_url:
        return "[redacted-url]"
    return url


def request_with_retry(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    json: object | None = None,
    data: object | None = None,
    timeout_override: float | None = None,
    retries: int | None = None,
    allowed_statuses: set[int] | None = None,
    redact_url: bool = False,
    idempotency_key: str | None = None,
) -> httpx.Response:
    max_retries = _get_int_env("BENJAMIN_HTTP_RETRIES", _DEFAULT_RETRIES) if retries is None else max(0, retries)
    backoff_base = max(0.01, _get_float_env("BENJAMIN_HTTP_BACKOFF_BASE_S", _DEFAULT_BACKOFF_BASE_S))
    backoff_max = max(0.01, _get_float_env("BENJAMIN_HTTP_BACKOFF_MAX_S", _DEFAULT_BACKOFF_MAX_S))

    merged_headers = dict(headers or {})
    if idempotency_key and "Idempotency-Key" not in merged_headers:
        merged_headers["Idempotency-Key"] = idempotency_key

    client = get_http_client()
    attempts = max_retries + 1
    safe_url = _safe_url(url, redact_url)

    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            response = client.request(
                method,
                url,
                headers=merged_headers or None,
                json=json,
                data=data,
                timeout=_build_timeout(timeout_override) if timeout_override is not None else None,
            )
        except _RETRYABLE_EXCEPTIONS as exc:
            last_exc = exc
            if attempt >= max_retries:
                raise BenjaminHTTPNetworkError(f"HTTP request failed after retries for {safe_url}: {exc.__class__.__name__}") from exc
            _sleep_for_retry(attempt, backoff_base, backoff_max)
            continue
        except httpx.HTTPError as exc:
            raise BenjaminHTTPNetworkError(f"HTTP request error for {safe_url}: {exc.__class__.__name__}") from exc

        status = response.status_code
        if allowed_statuses is not None and status in allowed_statuses:
            return response
        if 200 <= status < 300:
            return response
        if status in _RETRYABLE_STATUS_CODES and attempt < max_retries:
            _sleep_for_retry(attempt, backoff_base, backoff_max)
            continue
        raise BenjaminHTTPStatusError(f"HTTP status {status} for {safe_url}", status_code=status)

    raise BenjaminHTTPNetworkError(f"HTTP request failed for {safe_url}: {last_exc}")


def _sleep_for_retry(attempt: int, backoff_base: float, backoff_max: float) -> None:
    sleep_s = min(backoff_max, backoff_base * (2**attempt)) * (0.5 + random.random())
    time.sleep(sleep_s)
