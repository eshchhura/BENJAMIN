import logging
import types

try:
    import openai  # type: ignore
except Exception:  # pragma: no cover - provide dummy for tests
    openai = types.SimpleNamespace(
        chat=types.SimpleNamespace(
            completions=types.SimpleNamespace(create=lambda **_: types.SimpleNamespace(choices=[]))
        )
    )

from jarvis.config import Config

logger = logging.getLogger(__name__)

cfg = Config()
openai.api_key = cfg.get("api_keys", "openai")
ASSISTANT_NAME = cfg.get("assistant", "name", default="Assistant")


def can_handle(intent: str) -> bool:
    # Fallback skill for general conversation
    return True


def handle(request: dict) -> dict:
    intent = request.get("intent", "")
    params = request.get("entities", {})
    context = request.get("context", {})
    """Generate a response using OpenAI ChatGPT."""
    prompt = params.get("text", "")
    if not prompt:
        return {"text": "I'm not sure what you want me to talk about."}
    try:
        system_prompt = f"You are {ASSISTANT_NAME}, a helpful assistant."

        # Build chat history from recent turns if provided
        history = context.get("recent_turns", []) if context else []
        # Limit history to the last 5 turns to keep token usage small
        history = history[-5:]

        messages = [{"role": "system", "content": system_prompt}]
        for turn in history:
            user_msg = turn.get("input")
            if user_msg:
                messages.append({"role": "user", "content": user_msg})
            assistant_msg = turn.get("response")
            if assistant_msg:
                messages.append({"role": "assistant", "content": assistant_msg})

        # Current user prompt goes last
        messages.append({"role": "user", "content": prompt})

        resp = openai.chat.completions.create(model="gpt-3.5-turbo", messages=messages)
        msg = resp.choices[0].message.content.strip()
        return {"text": msg}
    except Exception as e:
        logger.exception("ChatGPT request failed: %s", e)
        return {"text": "Sorry, I couldn't think of a reply."}
