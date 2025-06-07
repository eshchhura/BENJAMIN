import logging
from typing import List

from jarvis.nlu.intent_recognizer import IntentRecognizer
from jarvis.nlu.dialogue_manager import DialogueManager
from jarvis.memory.short_term import ShortTermMemory
from jarvis.memory.long_term import LongTermMemory
from jarvis.memory.vector_store import VectorStore
from jarvis.utils.logger import get_logger


logger = get_logger(__name__)

class CoreController:
    """Central coordinator for processing user inputs."""

    def __init__(
        self,
        intent_recognizer: IntentRecognizer,
        dialogue_manager: DialogueManager,
        stm: ShortTermMemory,
        ltm: LongTermMemory,
        vector_store: VectorStore,
        skill_registry: List,
    ) -> None:
        self.intent_recognizer = intent_recognizer
        self.dialogue_manager = dialogue_manager
        self.stm = stm
        self.ltm = ltm
        self.vector_store = vector_store
        self.skill_registry = skill_registry

    def handle_input(self, text: str) -> str:
        """Process raw text and return a response string."""
        intent, entities = self.intent_recognizer.parse(text)

        context = self.stm.get_context()
        # Include vector store context if available
        if self.vector_store:
            try:
                indices, _ = self.vector_store.query_similar(text)
                context["similar_turns"] = [int(i) for i in indices if i != -1]
            except Exception as e:  # pragma: no cover - optional dependency
                logger.warning("Vector store query failed: %s", e)

        intent, entities = self.dialogue_manager.resolve_follow_up(intent, entities, context)
        entities["text"] = text

        response = self._dispatch_intent(intent, entities, context)

        self.stm.append(
            {"input": text, "intent": intent, "entities": entities, "response": response}
        )
        if self.ltm:
            try:
                self.ltm.log_interaction(text, intent, response)
            except Exception as e:  # pragma: no cover - optional dependency
                logger.warning("Failed to log interaction: %s", e)
        if self.vector_store:
            try:
                self.vector_store.add_turn(text)
            except Exception as e:  # pragma: no cover - optional dependency
                logger.warning("Vector store update failed: %s", e)

        return response

    def _dispatch_intent(self, intent: str, params: dict, context: dict) -> str:
        """Dispatch the intent to the first skill that can handle it."""
        ctx = dict(context) if context else {}
        ctx["recent_turns"] = self.stm.get_recent_turns()

        for skill in self.skill_registry:
            if skill.can_handle(intent):
                return skill.handle(intent, params, ctx)
        logger.warning("No skill found to handle intent '%s'", intent)
        return "Sorry, I didn’t understand that. Can you rephrase?"
