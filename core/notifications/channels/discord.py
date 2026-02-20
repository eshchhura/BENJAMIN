from __future__ import annotations

import json
from urllib import request


class DiscordWebhookNotifier:
    def __init__(self, webhook_url: str) -> None:
        self.webhook_url = webhook_url

    def send(self, title: str, body: str, meta: dict | None = None) -> None:
        content = f"**{title}**\n{body}"
        if meta:
            content += f"\nmeta: {json.dumps(meta, ensure_ascii=False)}"
        payload = json.dumps({"content": content}).encode("utf-8")
        req = request.Request(
            self.webhook_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=5):
            return
