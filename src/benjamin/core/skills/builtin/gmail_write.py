from __future__ import annotations

import json

from pydantic import BaseModel, Field

from benjamin.core.integrations.base import EmailConnector
from benjamin.core.skills.base import SkillResult


class GmailDraftEmailInput(BaseModel):
    to: list[str]
    cc: list[str] = Field(default_factory=list)
    bcc: list[str] = Field(default_factory=list)
    subject: str
    body: str


class GmailDraftEmailSkill:
    name = "gmail.draft_email"
    side_effect = "write"

    def __init__(self, connector: EmailConnector | None = None) -> None:
        self.connector = connector

    def run(self, query: str) -> SkillResult:
        payload = GmailDraftEmailInput.model_validate_json(query)
        if self.connector is None:
            raise RuntimeError("gmail_integration_unavailable")

        draft = self.connector.create_draft(
            to=payload.to,
            cc=payload.cc,
            bcc=payload.bcc,
            subject=payload.subject,
            body=payload.body,
        )
        return SkillResult(
            content=json.dumps(
                {
                    "draft_id": draft.get("draft_id", ""),
                    "subject": draft.get("subject", payload.subject),
                    "to": draft.get("to", payload.to),
                    "snippet": draft.get("snippet", ""),
                }
            )
        )
