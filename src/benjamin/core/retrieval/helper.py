from __future__ import annotations

import re

from benjamin.core.models.llm_provider import BenjaminLLM, LLMUnavailable


class RetrievalHelper:
    def __init__(self, llm: BenjaminLLM | None = None) -> None:
        self.llm = llm or BenjaminLLM()
        self.enabled = BenjaminLLM.feature_enabled("BENJAMIN_LLM_RETRIEVAL")

    def rewrite_query(self, user_text: str, target: str = "gmail") -> str:
        text = user_text.strip()
        if not text:
            return text
        if self.enabled:
            try:
                rewritten = self.llm.complete_text(
                    system="Rewrite natural language into concise search query syntax.",
                    user=f"Target={target}. Query={user_text}",
                    temperature=0.0,
                    max_tokens=128,
                ).strip()
                if rewritten:
                    return rewritten
            except LLMUnavailable:
                pass
        return self._fallback_rewrite(text=text, target=target)

    def rerank_candidates(self, user_text: str, candidates: list[dict], text_key: str) -> list[dict]:
        if not candidates:
            return []
        terms = [token for token in re.split(r"\W+", user_text.lower()) if token]
        scored = []
        for candidate in candidates:
            text = str(candidate.get(text_key, "")).lower()
            score = sum(1 for term in terms if term in text)
            scored.append((score, candidate))
        return [item for _, item in sorted(scored, key=lambda pair: pair[0], reverse=True)]

    def _fallback_rewrite(self, text: str, target: str) -> str:
        lowered = text.lower()
        if target == "gmail":
            if "from " in lowered:
                sender = lowered.split("from ", 1)[1].split()[0]
                return f"from:{sender} newer_than:7d"
            if "unread" in lowered:
                return "is:unread newer_than:7d"
        if target == "calendar" and "tomorrow" in lowered:
            return "tomorrow"
        return text
