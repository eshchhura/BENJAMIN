from __future__ import annotations

import json
import logging

from benjamin.core.http.client import request_with_retry
from benjamin.core.http.errors import BenjaminHTTPError

logger = logging.getLogger(__name__)


class DiscordWebhookNotifier:
    def __init__(self, webhook_url: str) -> None:
        self.webhook_url = webhook_url

    def send(self, title: str, body: str, meta: dict | None = None) -> None:
        content = f"**{title}**\n{body}"
        if meta:
            content += f"\nmeta: {json.dumps(meta, ensure_ascii=False)}"
        payload = {"content": content}
        try:
            request_with_retry(
                "POST",
                self.webhook_url,
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout_override=5.0,
                retries=1,
                redact_url=True,
            )
        except BenjaminHTTPError as exc:
            logger.warning("Discord webhook send failed: %s", exc)
