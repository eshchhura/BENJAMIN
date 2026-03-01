from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass

from benjamin.core.http.errors import BenjaminHTTPError

from .llm import LLM
from .llm_openai_compat import OpenAICompatClient


class LLMUnavailable(RuntimeError):
    pass


class LLMOutputError(RuntimeError):
    pass


@dataclass
class LLMConfig:
    provider: str
    model: str
    timeout_s: float
    temperature: float
    strict_json: bool
    max_tokens_json: int
    max_tokens_text: int


class BenjaminLLM:
    def __init__(self) -> None:
        provider = os.getenv("BENJAMIN_LLM_PROVIDER", "off").casefold()
        self.config = LLMConfig(
            provider=provider,
            model=os.getenv("BENJAMIN_LLM_MODEL", "zai-org/GLM-4.7"),
            timeout_s=float(os.getenv("BENJAMIN_LLM_TIMEOUT_S", "45")),
            temperature=float(os.getenv("BENJAMIN_LLM_TEMPERATURE", "0.2")),
            strict_json=os.getenv("BENJAMIN_LLM_STRICT_JSON", "on").casefold() == "on",
            max_tokens_json=int(os.getenv("BENJAMIN_LLM_MAX_TOKENS_JSON", "1200")),
            max_tokens_text=int(os.getenv("BENJAMIN_LLM_MAX_TOKENS_TEXT", "800")),
        )
        self._compat = OpenAICompatClient(
            url=os.getenv("BENJAMIN_VLLM_URL", "http://127.0.0.1:8001/v1/chat/completions"),
            model=self.config.model,
            timeout_s=self.config.timeout_s,
        )
        self._legacy = LLM()
        self.logger = logging.getLogger("benjamin.llm")

    @staticmethod
    def feature_enabled(name: str) -> bool:
        provider = os.getenv("BENJAMIN_LLM_PROVIDER", "off").casefold()
        default = "on" if provider != "off" else "off"
        return os.getenv(name, default).casefold() == "on"

    def complete_text(self, system: str, user: str, max_tokens: int | None = None, temperature: float | None = None) -> str:
        used_tokens = max_tokens or self.config.max_tokens_text
        used_temp = self.config.temperature if temperature is None else temperature
        return self._call(system=system, user=user, max_tokens=used_tokens, temperature=used_temp, mode="text")

    def complete_json(self, system: str, user: str, schema_hint: dict | None = None, max_tokens: int | None = None) -> dict:
        used_tokens = max_tokens or self.config.max_tokens_json
        strict_instruction = (
            "Return strict JSON only with no markdown fences and no prose."
            if self.config.strict_json
            else "Return JSON."
        )
        schema_block = f"Schema hint: {json.dumps(schema_hint, ensure_ascii=False)}\n" if schema_hint else ""
        raw = self._call(
            system=system,
            user=f"{strict_instruction}\n{schema_block}{user}",
            max_tokens=used_tokens,
            temperature=0.0,
            response_format={"type": "json_object"} if self.config.provider in {"vllm", "http"} else None,
            mode="json",
        )
        parsed = self._parse_json(raw)
        if parsed is None:
            if self.config.strict_json:
                raise LLMOutputError("Could not parse JSON response")
            return {}
        return parsed

    def _call(
        self,
        system: str,
        user: str,
        max_tokens: int,
        temperature: float,
        response_format: dict | None = None,
        mode: str = "text",
    ) -> str:
        if self.config.provider == "off":
            raise LLMUnavailable("LLM provider is off")

        start = time.perf_counter()
        last_error: Exception | None = None
        for _ in range(2):
            try:
                if self.config.provider in {"vllm", "http"}:
                    output = self._compat.chat_completion(
                        system=system,
                        user=user,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        response_format=response_format,
                    )
                else:
                    output = self._legacy.complete(f"{system}\n\n{user}")
                self.logger.info(
                    "llm_call",
                    extra={
                        "extra_fields": {
                            "provider": self.config.provider,
                            "model": self.config.model,
                            "mode": mode,
                            "duration_ms": int((time.perf_counter() - start) * 1000),
                            "ok": True,
                            "system_len": len(system),
                            "user_len": len(user),
                        }
                    },
                )
                return output
            except (BenjaminHTTPError, ValueError) as exc:
                last_error = exc
                continue

        self.logger.info(
            "llm_call",
            extra={
                "extra_fields": {
                    "provider": self.config.provider,
                    "model": self.config.model,
                    "mode": mode,
                    "duration_ms": int((time.perf_counter() - start) * 1000),
                    "ok": False,
                    "system_len": len(system),
                    "user_len": len(user),
                }
            },
        )
        raise LLMUnavailable(f"LLM request failed: {last_error}")

    def _parse_json(self, raw: str) -> dict | None:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end < start:
            return None
        snippet = cleaned[start : end + 1]
        try:
            parsed = json.loads(snippet)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
