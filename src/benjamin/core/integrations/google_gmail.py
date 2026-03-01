from __future__ import annotations

import base64
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import parsedate_to_datetime

from benjamin.core.infra.breaker_manager import BreakerManager
from benjamin.core.integrations.google_auth import build_google_service


class GoogleGmailConnector:
    def __init__(self, token_path: str, breaker_manager: BreakerManager | None = None) -> None:
        self.service = build_google_service("gmail", "v1", token_path)
        self.breaker_manager = breaker_manager

    def search_messages(self, query: str, max_results: int) -> list[dict]:
        def _call() -> list[dict]:
            response = self.service.users().messages().list(userId="me", q=query, maxResults=max_results).execute()
            out: list[dict] = []
            for item in response.get("messages", []):
                out.append(self._normalize_message(item["id"]))
            return out

        return self._guarded(_call)

    def read_message(self, message_id: str) -> dict:
        return self._guarded(lambda: self._normalize_message(message_id, include_body=True))

    def thread_summary(self, thread_id: str, max_messages: int = 10) -> dict:
        def _call() -> dict:
            thread = self.service.users().threads().get(userId="me", id=thread_id, format="metadata").execute()
            messages = thread.get("messages", [])[:max_messages]
            participants: set[str] = set()
            snippets: list[str] = []
            subject = ""
            for msg in messages:
                headers = self._headers_map(msg.get("payload", {}).get("headers", []))
                if headers.get("From"):
                    participants.add(headers["From"])
                if headers.get("To"):
                    participants.add(headers["To"])
                if not subject:
                    subject = headers.get("Subject", "")
                snippet = msg.get("snippet")
                if snippet:
                    snippets.append(snippet)

            return {
                "thread_id": thread_id,
                "subject": subject,
                "participants": sorted(participants),
                "snippets": snippets,
            }

        return self._guarded(_call)

    def create_draft(
        self,
        to: list[str],
        cc: list[str] | None,
        bcc: list[str] | None,
        subject: str,
        body: str,
    ) -> dict:
        def _call() -> dict:
            message = EmailMessage()
            message["To"] = ", ".join(to)
            if cc:
                message["Cc"] = ", ".join(cc)
            if bcc:
                message["Bcc"] = ", ".join(bcc)
            message["Subject"] = subject
            message.set_content(body)

            encoded = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
            response = (
                self.service.users()
                .drafts()
                .create(userId="me", body={"message": {"raw": encoded}})
                .execute()
            )
            draft = response.get("message", {})
            snippet = draft.get("snippet") or body[:200]
            return {
                "draft_id": response.get("id") or draft.get("id"),
                "subject": subject,
                "to": to,
                "snippet": snippet,
            }

        try:
            return self._guarded(_call)
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(f"google_gmail_create_draft_failed: {exc}") from exc

    def _guarded(self, fn):
        if self.breaker_manager is None:
            return fn()
        return self.breaker_manager.wrap("gmail", fn)

    def _normalize_message(self, message_id: str, include_body: bool = False) -> dict:
        format_kind = "full" if include_body else "metadata"
        message = self.service.users().messages().get(userId="me", id=message_id, format=format_kind).execute()
        headers = self._headers_map(message.get("payload", {}).get("headers", []))

        date_iso = self._to_iso(headers.get("Date"))
        payload = {
            "id": message.get("id"),
            "thread_id": message.get("threadId"),
            "from": headers.get("From", ""),
            "subject": headers.get("Subject", ""),
            "snippet": message.get("snippet", ""),
            "date_iso": date_iso,
        }
        if include_body:
            payload["body"] = self._extract_text_body(message.get("payload", {}))
        return payload

    def _headers_map(self, headers: list[dict]) -> dict[str, str]:
        return {header.get("name", ""): header.get("value", "") for header in headers}

    def _to_iso(self, date_header: str | None) -> str | None:
        if not date_header:
            return None
        try:
            parsed = parsedate_to_datetime(date_header)
        except (TypeError, ValueError):
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat()

    def _extract_text_body(self, payload: dict) -> str:
        mime_type = payload.get("mimeType")
        body_data = payload.get("body", {}).get("data")
        if mime_type == "text/plain" and body_data:
            return self._decode_body(body_data)

        for part in payload.get("parts", []):
            if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
                return self._decode_body(part["body"]["data"])

        return ""

    def _decode_body(self, data: str) -> str:
        padded = data + "=" * (-len(data) % 4)
        return base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8", errors="replace")
