from __future__ import annotations

from benjamin.core.net.http import request_json


class OpenAICompatClient:
    def __init__(self, url: str, model: str, timeout_s: float = 45.0) -> None:
        self.url = url
        self.model = model
        self.timeout_s = timeout_s

    def chat_completion(
        self,
        system: str,
        user: str,
        temperature: float,
        max_tokens: int,
        response_format: dict | None = None,
    ) -> str:
        payload: dict[str, object] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format is not None:
            payload["response_format"] = response_format

        data = request_json(
            "POST",
            self.url,
            json=payload,
            timeout_s=self.timeout_s,
        )
        choices = data.get("choices") or []
        if not choices:
            return ""
        message = choices[0].get("message") or {}
        return str(message.get("content") or "")
