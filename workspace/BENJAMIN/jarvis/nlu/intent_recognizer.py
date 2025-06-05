# jarvis/nlu/intent_recognizer.py
# -----------------------------------
# Wraps Rasa or spaCy to classify intents and extract entities from raw text.
# -----------------------------------

import os
import logging

from rasa.nlu.model import Interpreter  # If using Rasa

logger = logging.getLogger(__name__)

class IntentRecognizer:
    """
    Loads a pretrained Rasa NLU model (under models/nlu_model).
    `parse(text)` → (intent: str, entities: dict)
    """
    def __init__(self, model_path="models/nlu_model"):
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"NLU model not found at {model_path}. Train with scripts/train_nlu.py")
        self.interpreter = Interpreter.load(model_path)
        logger.info("IntentRecognizer loaded Rasa model from %s.", model_path)

    def parse(self, text: str):
        """
        Returns:
            intent_name (str): The top-scoring intent.
            entities (dict): Mapping from entity names to values.
        """
        result = self.interpreter.parse(text)
        intent_name = result.get("intent", {}).get("name", "")
        entities = {e["entity"]: e["value"] for e in result.get("entities", [])}
        logger.debug("Parsed intent: %s, entities: %s", intent_name, entities)
        return intent_name, entities
