from __future__ import annotations

import httpx


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

        response = httpx.post(self.url, json=payload, timeout=self.timeout_s)
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            return ""
        message = choices[0].get("message") or {}
        return str(message.get("content") or "")
