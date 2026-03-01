from __future__ import annotations

import os
import random
import threading
import time
from typing import Any

import httpx


class HTTPRequestError(RuntimeError):
    pass


class HTTPTimeoutError(HTTPRequestError):
    pass


class HTTPConnectionError(HTTPRequestError):
    pass


class HTTPRateLimitError(HTTPRequestError):
    pass


class HTTPServerError(HTTPRequestError):
    pass


class HTTPClientError(HTTPRequestError):
    pass


_DEFAULT_TIMEOUT_S = 10.0
_DEFAULT_RETRIES = 2
_DEFAULT_BACKOFF_BASE_MS = 250
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


def _timeout(timeout_s: float | None = None) -> float:
    return max(0.1, timeout_s if timeout_s is not None else _get_float_env("BENJAMIN_HTTP_TIMEOUT_S", _DEFAULT_TIMEOUT_S))


def get_http_client() -> httpx.Client:
    global _client
    if _client is not None:
        return _client
    with _client_lock:
        if _client is None:
            _client = httpx.Client(timeout=_timeout(), headers={"User-Agent": os.getenv("BENJAMIN_HTTP_USER_AGENT", _DEFAULT_USER_AGENT)})
    return _client


def request_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    json: Any = None,
    timeout_s: float | None = None,
    retries: int | None = None,
    backoff_base_ms: int | None = None,
) -> dict[str, Any]:
    max_retries = _get_int_env("BENJAMIN_HTTP_RETRIES", _DEFAULT_RETRIES) if retries is None else max(0, retries)
    base_ms = _get_int_env("BENJAMIN_HTTP_BACKOFF_BASE_MS", _DEFAULT_BACKOFF_BASE_MS) if backoff_base_ms is None else max(1, backoff_base_ms)

    client = get_http_client()
    attempts = max_retries + 1

    for attempt in range(attempts):
        try:
            response = client.request(method=method, url=url, headers=headers, json=json, timeout=_timeout(timeout_s))
        except httpx.TimeoutException as exc:
            if attempt >= max_retries:
                raise HTTPTimeoutError(f"request_timeout:{method}:{url}") from exc
            _sleep_backoff(attempt, base_ms)
            continue
        except (httpx.ConnectError, httpx.NetworkError, httpx.RemoteProtocolError) as exc:
            if attempt >= max_retries:
                raise HTTPConnectionError(f"request_connection_error:{method}:{url}") from exc
            _sleep_backoff(attempt, base_ms)
            continue
        except httpx.HTTPError as exc:
            raise HTTPConnectionError(f"request_http_error:{method}:{url}:{exc.__class__.__name__}") from exc

        if 200 <= response.status_code < 300:
            payload = response.json()
            return payload if isinstance(payload, dict) else {"data": payload}

        if response.status_code == 429:
            if attempt >= max_retries:
                raise HTTPRateLimitError(f"request_rate_limited:{method}:{url}")
            _sleep_backoff(attempt, base_ms)
            continue

        if response.status_code >= 500:
            if attempt >= max_retries:
                raise HTTPServerError(f"request_server_error:{response.status_code}:{method}:{url}")
            _sleep_backoff(attempt, base_ms)
            continue

        raise HTTPClientError(f"request_client_error:{response.status_code}:{method}:{url}")

    raise HTTPRequestError(f"request_unknown_error:{method}:{url}")


def _sleep_backoff(attempt: int, base_ms: int) -> None:
    jitter_ms = random.randint(0, max(1, base_ms // 4))
    sleep_ms = (base_ms * (2**attempt)) + jitter_ms
    time.sleep(sleep_ms / 1000.0)
