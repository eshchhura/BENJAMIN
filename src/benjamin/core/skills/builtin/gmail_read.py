from __future__ import annotations

import json

from pydantic import BaseModel

from benjamin.core.integrations.base import EmailConnector
from benjamin.core.skills.base import SkillResult


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

    def __init__(self, connector: EmailConnector | None = None) -> None:
        self.connector = connector

    def run(self, query: str) -> SkillResult:
        payload = GmailSearchInput.model_validate_json(query)
        if self.connector is None:
            return SkillResult(content=json.dumps({"messages": [], "reason": "gmail_integration_unavailable"}))

        messages = self.connector.search_messages(query=payload.query, max_results=payload.max_results)
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
        return SkillResult(content=json.dumps({"messages": normalized}))


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

    def __init__(self, connector: EmailConnector | None = None) -> None:
        self.connector = connector

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
        return SkillResult(
            content=json.dumps(
                {
                    "thread_id": summary.get("thread_id", payload.thread_id),
                    "subject": summary.get("subject", ""),
                    "participants": summary.get("participants", []),
                    "snippets": summary.get("snippets", []),
                }
            )
        )
