"""Provider-agnostic LLM client with optional HTTP mode."""

from __future__ import annotations

import os
from typing import Any

import httpx


class LLMClient:
    """Thin client that asks an LLM service for JSON output."""

    def __init__(self) -> None:
        self.mode = os.getenv("BENJAMIN_LLM_MODE", "off").strip().lower() or "off"
        self.http_url = os.getenv("BENJAMIN_LLM_HTTP_URL", "").strip()
        self.http_token = os.getenv("BENJAMIN_LLM_HTTP_TOKEN", "").strip()

    def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema_hint: dict[str, Any],
    ) -> dict[str, Any]:
        """Return a JSON object from configured LLM provider."""

        if self.mode == "off":
            raise RuntimeError("LLM mode is off")

        if self.mode != "http":
            raise RuntimeError(f"Unsupported LLM mode: {self.mode}")

        if not self.http_url:
            raise RuntimeError("BENJAMIN_LLM_HTTP_URL is required for http mode")

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.http_token:
            headers["Authorization"] = f"Bearer {self.http_token}"

        payload = {
            "system": system_prompt,
            "user": user_prompt,
            "schema": json_schema_hint,
        }

        with httpx.Client(timeout=15.0) as client:
            response = client.post(self.http_url, json=payload, headers=headers)
            response.raise_for_status()
            body = response.json()

        plan_json = body.get("json")
        if not isinstance(plan_json, dict):
            raise RuntimeError("LLM response must contain object field 'json'")
        return plan_json
