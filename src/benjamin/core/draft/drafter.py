from __future__ import annotations

from benjamin.core.models.llm_provider import BenjaminLLM, LLMUnavailable


class Drafter:
    def __init__(self, llm: BenjaminLLM | None = None) -> None:
        self.llm = llm or BenjaminLLM()
        self.enabled = BenjaminLLM.feature_enabled("BENJAMIN_LLM_DRAFTER")

    def draft_email(self, to: list[str], subject: str, context_text: str, tone: str = "neutral") -> str:
        if self.enabled:
            try:
                return self.llm.complete_text(
                    system="Draft professional emails.",
                    user=(
                        f"Recipients: {', '.join(to)}\nSubject: {subject}\nTone: {tone}\n"
                        f"Context:\n{context_text}\n\nReturn only body text."
                    ),
                ).strip()
            except LLMUnavailable:
                pass
        return f"Hi,\n\n{context_text}\n\nBest,\nBenjamin"

    def draft_calendar_agenda(self, title: str, context_text: str) -> str:
        if self.enabled:
            try:
                return self.llm.complete_text(
                    system="Draft concise meeting agendas.",
                    user=f"Title: {title}\nContext:\n{context_text}",
                ).strip()
            except LLMUnavailable:
                pass
        return f"Agenda for {title}:\n- Objective\n- Discussion\n- Next steps\n\nNotes: {context_text[:200]}"
