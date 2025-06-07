"""Rasa NLU interpreter wrapper.

This module provides a simple wrapper around ``rasa.nlu.model.Interpreter``
to make it compatible with the ``IntentRecognizer`` interface used by
``JarvisAssistant``.
"""

from __future__ import annotations

import logging
from typing import Dict, Tuple

from rasa.nlu.model import Interpreter

logger = logging.getLogger(__name__)


class RasaInterpreter:
    """Load a Rasa NLU model and expose a ``parse`` method."""

    def __init__(self, model_path: str = "models/rasa_nlu") -> None:
        self.model_path = model_path
        try:
            self.interpreter = Interpreter.load(model_path)
        except Exception as exc:  # pragma: no cover - handled by Rasa
            logger.error("Failed to load Rasa model from %s: %s", model_path, exc)
            raise

    def parse(self, text: str) -> Tuple[str, Dict[str, str]]:
        """Return ``(intent, entities)`` for the supplied ``text``."""
        result = self.interpreter.parse(text)
        intent = result.get("intent", {}).get("name", "unknown")
        entities = {ent["entity"]: ent["value"] for ent in result.get("entities", [])}
        logger.debug("Parsed intent %s with entities %s", intent, entities)
        return intent, entities
