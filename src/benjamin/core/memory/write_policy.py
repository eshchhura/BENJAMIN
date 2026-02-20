from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class MemoryDecision:
    save: bool
    reason: str


class MemoryWritePolicy:
    def should_save(self, text: str) -> MemoryDecision:
        if len(text.strip()) < 10:
            return MemoryDecision(save=False, reason="Too short")
        return MemoryDecision(save=True, reason="Useful context")


class WritePolicy:
    _PREFERENCE_PATTERNS = (
        "from now on",
        "always",
        "never",
        "remember that",
        "my preference is",
    )

    def propose_writes(self, user_message: str, assistant_answer: str) -> dict[str, list[dict[str, Any]]]:
        semantic_upserts: list[dict[str, Any]] = []
        lowered = user_message.casefold()

        if any(pattern in lowered for pattern in self._PREFERENCE_PATTERNS):
            key_slug = self._slugify(user_message)[:48] or "user"
            semantic_upserts.append(
                {
                    "key": f"preference:{key_slug}",
                    "value": user_message.strip(),
                    "scope": "global",
                    "tags": ["preference", "autowrite"],
                }
            )

        episodes = [
            {
                "kind": "task",
                "summary": f"User asked: {self._shorten(user_message)}. Assistant: {self._shorten(assistant_answer)}.",
                "meta": {},
            }
        ]

        return {"semantic_upserts": semantic_upserts, "episodes": episodes}

    def _slugify(self, text: str) -> str:
        words = re.findall(r"[a-z0-9]+", text.casefold())
        return "-".join(words[:8])

    def _shorten(self, text: str, limit: int = 120) -> str:
        compact = " ".join(text.split())
        if len(compact) <= limit:
            return compact
        return compact[: limit - 1].rstrip() + "…"
