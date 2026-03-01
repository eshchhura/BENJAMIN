from __future__ import annotations

import re

from benjamin.core.models.llm_provider import BenjaminLLM, LLMUnavailable


class Summarizer:
    def __init__(self, llm: BenjaminLLM | None = None) -> None:
        self.llm = llm or BenjaminLLM()
        self.enabled = BenjaminLLM.feature_enabled("BENJAMIN_LLM_SUMMARIZER")

    def summarize_bullets(self, text: str, max_bullets: int = 6) -> list[str]:
        if not text.strip():
            return []
        if self.enabled:
            try:
                response = self.llm.complete_text(
                    system="Summarize email threads into concise bullet points.",
                    user=f"Return up to {max_bullets} bullet points for:\n{text}",
                )
                bullets = [line.strip("-• \t") for line in response.splitlines() if line.strip()]
                if bullets:
                    return bullets[:max_bullets]
            except LLMUnavailable:
                pass
        return self._fallback_bullets(text, max_bullets=max_bullets)

    def compress_briefing(self, sections: dict[str, str]) -> str:
        non_empty = {k: v for k, v in sections.items() if v.strip()}
        if not non_empty:
            return ""
        merged = "\n\n".join(f"{k}:\n{v}" for k, v in non_empty.items())
        if self.enabled:
            try:
                response = self.llm.complete_text(
                    system="Create a concise prioritized daily briefing.",
                    user=f"Compress these sections into one narrative:\n{merged}",
                )
                if response.strip():
                    return response.strip()
            except LLMUnavailable:
                pass
        return "\n\n".join(f"{k}:\n{v}" for k, v in non_empty.items())

    def _fallback_bullets(self, text: str, max_bullets: int) -> list[str]:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            lines = [part.strip() for part in re.split(r"[.!?]", text) if part.strip()]
        return [line[:140] for line in lines[:max_bullets]]
