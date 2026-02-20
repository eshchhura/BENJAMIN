from __future__ import annotations

import os
from typing import Protocol

from .channels.console import ConsoleNotifier
from .channels.discord import DiscordWebhookNotifier


class Notifier(Protocol):
    def send(self, title: str, body: str, meta: dict | None = None) -> None: ...


class NotificationRouter:
    def __init__(self, channels: list[Notifier]) -> None:
        self.channels = channels

    def send(self, title: str, body: str, meta: dict | None = None) -> None:
        payload_meta = meta or {}
        for channel in self.channels:
            channel.send(title=title, body=body, meta=payload_meta)


def build_notification_router() -> NotificationRouter:
    configured = os.getenv("BENJAMIN_NOTIFIER", "console")
    requested = [name.strip().casefold() for name in configured.split(",") if name.strip()]
    channels: list[Notifier] = []

    if "console" in requested or not requested:
        channels.append(ConsoleNotifier())

    if "discord" in requested:
        webhook = os.getenv("BENJAMIN_DISCORD_WEBHOOK_URL")
        if webhook:
            channels.append(DiscordWebhookNotifier(webhook_url=webhook))
        else:
            print("[notifications] discord notifier requested but BENJAMIN_DISCORD_WEBHOOK_URL is not set; skipping")

    if not channels:
        channels.append(ConsoleNotifier())

    return NotificationRouter(channels=channels)
