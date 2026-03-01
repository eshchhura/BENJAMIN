from __future__ import annotations

from benjamin.core.cache.ttl import TTLCache


def test_ttl_cache_get_or_set_computes_once_within_ttl() -> None:
    cache = TTLCache(default_ttl_s=10)
    counter = {"count": 0}

    def compute() -> bool:
        counter["count"] += 1
        return True

    first = cache.get_or_set("llm_ping:vllm:http://x", 10, compute)
    second = cache.get_or_set("llm_ping:vllm:http://x", 10, compute)

    assert first is True
    assert second is True
    assert counter["count"] == 1
