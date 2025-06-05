# jarvis/nlu/dialogue_manager.py
# -----------------------------------
# Maintains conversational context, handles follow-up/clarification.
# -----------------------------------

import logging

logger = logging.getLogger(__name__)

class DialogueManager:
    """
    Simple dialogue state tracker. Given a new (intent, entities) plus recent context,
    determine if this is a follow-up (e.g., user said “Actually, change it to Friday”).
    If so, adjust intent/entities accordingly.
    """

    def __init__(self):
        # Example: map follow-up intents; can be extended or replaced by Rasa Core
        self.follow_up_map = {
            "change_date": ["reminder"],
            # etc.
        }

    def resolve_follow_up(self, intent: str, entities: dict, context: dict):
        """
        If the current intent is a known follow-up, merge with previous intent from context.
        Args:
            intent: new intent name
            entities: new entities dict
            context: recent conversation context (from STM)
        Returns:
            (resolved_intent, resolved_entities)
        """
        if intent in self.follow_up_map:
            previous_intent = context.get("last_intent")
            if previous_intent in self.follow_up_map[intent]:
                # Merge entities (this is a simplistic example)
                merged_intent = previous_intent
                merged_entities = {**context.get("last_entities", {}), **entities}
                logger.info("Resolved follow-up: %s -> %s", intent, merged_intent)
                return merged_intent, merged_entities
        # No follow-up detected; store in context externally
        return intent, entities
