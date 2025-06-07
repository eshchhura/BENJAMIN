# jarvis/memory/cache.py
# -----------------------------------
# Simple in-memory LRU cache used by memory components.
# -----------------------------------

from collections import OrderedDict
from typing import Any

class LRUCache:
    """Lightweight LRU cache storing the most recent items."""

    def __init__(self, maxsize: int = 128) -> None:
        self.maxsize = maxsize
        self._cache: OrderedDict[Any, Any] = OrderedDict()

    def get(self, key: Any) -> Any:
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def set(self, key: Any, value: Any) -> None:
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = value
        if len(self._cache) > self.maxsize:
            self._cache.popitem(last=False)

    def clear(self) -> None:
        self._cache.clear()
