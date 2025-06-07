"""Redis-backed short term memory implementation."""

from __future__ import annotations

import json
from typing import List

try:
    import redis  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    redis = None


class RedisStore:
    def __init__(self, url: str = "redis://localhost:6379/0", capacity: int = 50) -> None:
        if redis is None:
            raise RuntimeError("Redis package not available")
        self.client = redis.Redis.from_url(url, decode_responses=True)
        self.capacity = capacity
        self.key = "jarvis:stm"

    def append(self, turn: dict) -> None:
        data = json.dumps(turn)
        self.client.lpush(self.key, data)
        self.client.ltrim(self.key, 0, self.capacity - 1)

    def get_recent_turns(self) -> List[dict]:
        items = self.client.lrange(self.key, 0, self.capacity - 1)
        return [json.loads(i) for i in reversed(items)]

    def get_context(self) -> dict:
        turns = self.get_recent_turns()
        if not turns:
            return {}
        last = turns[-1]
        return {"last_intent": last.get("intent"), "last_entities": last.get("entities")}
