from __future__ import annotations


class ConsoleNotifier:
    def send(self, title: str, body: str, meta: dict | None = None) -> None:
        print(f"[notification] {title}\n{body}\nmeta={meta or {}}")
