from __future__ import annotations

import threading
import time
from collections.abc import Callable


class TTLCache:
    def __init__(self, default_ttl_s: int) -> None:
        self.default_ttl_s = max(1, int(default_ttl_s))
        self._data: dict[str, tuple[float, object]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> object | None:
        now = time.monotonic()
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if expires_at <= now:
                self._data.pop(key, None)
                return None
            return value

    def set(self, key: str, value: object, ttl_s: int | None = None) -> None:
        ttl_value = self.default_ttl_s if ttl_s is None else max(1, int(ttl_s))
        expires_at = time.monotonic() + ttl_value
        with self._lock:
            self._data[key] = (expires_at, value)

    def get_or_set(self, key: str, ttl_s: int, fn: Callable[[], object]) -> object:
        with self._lock:
            now = time.monotonic()
            entry = self._data.get(key)
            if entry is not None:
                expires_at, value = entry
                if expires_at > now:
                    return value
                self._data.pop(key, None)

            value = fn()
            expires_at = time.monotonic() + max(1, int(ttl_s))
            self._data[key] = (expires_at, value)
            return value
