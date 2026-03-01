from __future__ import annotations

import json

from pydantic import BaseModel

from benjamin.core.integrations.base import EmailConnector
from benjamin.core.retrieval.helper import RetrievalHelper
from benjamin.core.skills.base import SkillResult
from benjamin.core.summarize.summarizer import Summarizer


class GmailSearchInput(BaseModel):
    query: str
    max_results: int = 10


class GmailReadMessageInput(BaseModel):
    message_id: str


class GmailThreadSummaryInput(BaseModel):
    thread_id: str
    max_messages: int = 10


class GmailSearchSkill:
    name = "gmail.search"
    side_effect = "read"

    def __init__(self, connector: EmailConnector | None = None, retrieval_helper: RetrievalHelper | None = None) -> None:
        self.connector = connector
        self.retrieval_helper = retrieval_helper or RetrievalHelper()

    def run(self, query: str) -> SkillResult:
        payload = GmailSearchInput.model_validate_json(query)
        if self.connector is None:
            return SkillResult(content=json.dumps({"messages": [], "reason": "gmail_integration_unavailable"}))

        rewritten_query = payload.query
        if ":" not in payload.query and " label:" not in payload.query:
            rewritten_query = self.retrieval_helper.rewrite_query(payload.query, target="gmail")

        messages = self.connector.search_messages(query=rewritten_query, max_results=payload.max_results)
        normalized = [
            {
                "from": item.get("from", ""),
                "subject": item.get("subject", ""),
                "snippet": item.get("snippet", ""),
                "date_iso": item.get("date_iso"),
                "thread_id": item.get("thread_id"),
            }
            for item in messages
        ]
        ranked = self.retrieval_helper.rerank_candidates(payload.query, normalized, text_key="snippet")
        return SkillResult(content=json.dumps({"messages": ranked, "query_used": rewritten_query}))


class GmailReadMessageSkill:
    name = "gmail.read_message"
    side_effect = "read"

    def __init__(self, connector: EmailConnector | None = None) -> None:
        self.connector = connector

    def run(self, query: str) -> SkillResult:
        payload = GmailReadMessageInput.model_validate_json(query)
        if self.connector is None:
            return SkillResult(content=json.dumps({"message_id": payload.message_id, "reason": "gmail_integration_unavailable"}))

        message = self.connector.read_message(payload.message_id)
        return SkillResult(
            content=json.dumps(
                {
                    "message_id": payload.message_id,
                    "subject": message.get("subject", ""),
                    "from": message.get("from", ""),
                    "body": message.get("body", ""),
                }
            )
        )


class GmailThreadSummarySkill:
    name = "gmail.thread_summary"
    side_effect = "read"

    def __init__(self, connector: EmailConnector | None = None, summarizer: Summarizer | None = None) -> None:
        self.connector = connector
        self.summarizer = summarizer or Summarizer()

    def run(self, query: str) -> SkillResult:
        payload = GmailThreadSummaryInput.model_validate_json(query)
        if self.connector is None:
            return SkillResult(
                content=json.dumps(
                    {
                        "thread_id": payload.thread_id,
                        "subject": "",
                        "participants": [],
                        "snippets": [],
                        "reason": "gmail_integration_unavailable",
                    }
                )
            )

        summary = self.connector.thread_summary(payload.thread_id, max_messages=payload.max_messages)
        snippets = summary.get("snippets", [])
        bullets = self.summarizer.summarize_bullets("\n".join(snippets), max_bullets=6) if snippets else snippets
        return SkillResult(
            content=json.dumps(
                {
                    "thread_id": summary.get("thread_id", payload.thread_id),
                    "subject": summary.get("subject", ""),
                    "participants": summary.get("participants", []),
                    "snippets": snippets,
                    "bullets": bullets,
                }
            )
        )
