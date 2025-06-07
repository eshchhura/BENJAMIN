import logging
import openai
from jarvis.config import Config

logger = logging.getLogger(__name__)

cfg = Config()
openai.api_key = cfg.get("api_keys", "openai")
ASSISTANT_NAME = cfg.get("assistant", "name", default="Assistant")


def can_handle(intent: str) -> bool:
    # Fallback skill for general conversation
    return True


def handle(intent: str, params: dict, context: dict) -> str:
    """Generate a response using OpenAI ChatGPT."""
    prompt = params.get("text", "")
    if not prompt:
        return "I'm not sure what you want me to talk about."
    try:
        system_prompt = f"You are {ASSISTANT_NAME}, a helpful assistant."
        resp = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
        )
        msg = resp.choices[0].message.content.strip()
        return msg
    except Exception as e:
        logger.exception("ChatGPT request failed: %s", e)
        return "Sorry, I couldn't think of a reply."
