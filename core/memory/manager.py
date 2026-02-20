from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .episodic import EpisodicMemoryStore
from .semantic import SemanticMemoryStore
from .write_policy import WritePolicy


class MemoryManager:
    def __init__(
        self,
        state_dir: Path | None = None,
        policy: WritePolicy | None = None,
        autowrite: bool | None = None,
    ) -> None:
        self.state_dir = state_dir or self._default_state_dir()
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.semantic = SemanticMemoryStore(self.state_dir / "semantic.jsonl")
        self.episodic = EpisodicMemoryStore(self.state_dir / "episodic.jsonl")
        self.policy = policy or WritePolicy()
        self.autowrite_enabled = self._resolve_autowrite(autowrite)

    def _resolve_autowrite(self, autowrite: bool | None) -> bool:
        if autowrite is not None:
            return autowrite
        return os.getenv("BENJAMIN_MEMORY_AUTOWRITE", "on").casefold() != "off"

    def _default_state_dir(self) -> Path:
        configured = os.getenv("BENJAMIN_STATE_DIR")
        if configured:
            return Path(configured).expanduser()
        return Path.home() / ".benjamin"

    def retrieve_context(self, text: str, limit: int = 8) -> dict[str, list[Any]]:
        semantic_limit = max(1, limit // 2)
        episodic_limit = max(1, limit - semantic_limit)
        return {
            "semantic": self.semantic.search(text, semantic_limit),
            "episodic": self.episodic.search(text, episodic_limit),
        }

    def propose_writes(self, user_message: str, assistant_answer: str) -> dict[str, list[dict[str, Any]]]:
        return self.policy.propose_writes(user_message=user_message, assistant_answer=assistant_answer)

    def commit(self, proposal: dict[str, list[dict[str, Any]]]) -> dict[str, int]:
        semantic_count = 0
        for upsert in proposal.get("semantic_upserts", []):
            self.semantic.upsert(**upsert)
            semantic_count += 1

        episodic_count = 0
        for episode in proposal.get("episodes", []):
            self.episodic.append(**episode)
            episodic_count += 1

        return {"semantic_count": semantic_count, "episodic_count": episodic_count}
