from __future__ import annotations

from benjamin.core.http.errors import BenjaminHTTPNetworkError
from benjamin.core.notifications.channels.discord import DiscordWebhookNotifier


def test_discord_notifier_http_failure_is_graceful(monkeypatch) -> None:
    notifier = DiscordWebhookNotifier(webhook_url="https://discord.example/webhook")

    def always_fail(*args, **kwargs):
        raise BenjaminHTTPNetworkError("boom")

    monkeypatch.setattr("benjamin.core.notifications.channels.discord.request_with_retry", always_fail)

    notifier.send(title="Test", body="Body", meta={"kind": "job"})
