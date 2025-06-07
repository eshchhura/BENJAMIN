"""Abstract interfaces for NLU recognizers."""

from __future__ import annotations

import logging
from typing import Dict, Tuple, Protocol

from .intent_recognizer import IntentRecognizer

logger = logging.getLogger(__name__)


class Recognizer(Protocol):
    """Protocol for intent recognizers."""

    def parse(self, text: str) -> Tuple[str, Dict[str, str]]:
        """Return intent name and extracted entities."""
        ...


class RasaNLUAdapter:
    """Wrapper around Rasa interpreter with spaCy fallback."""

    def __init__(self, model_path: str = "models/rasa_nlu") -> None:
        try:
            from .rasa_interpreter import RasaInterpreter

            self.interpreter = RasaInterpreter(model_path)
        except Exception as exc:  # pragma: no cover - optional dependency
            logger.error("Failed to load Rasa interpreter: %s", exc)
            self.interpreter = None
        self.fallback = IntentRecognizer()

    def parse(self, text: str) -> Tuple[str, Dict[str, str]]:
        if self.interpreter is not None:
            try:
                return self.interpreter.parse(text)
            except Exception as exc:  # pragma: no cover - Rasa errors
                logger.warning("Rasa parse failed: %s; falling back to spaCy", exc)
        return self.fallback.parse(text)
