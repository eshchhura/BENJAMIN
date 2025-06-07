# jarvis/main.py
# -----------------------------
# Entry point for the Jarvis assistant.
# Initializes interfaces, NLU, skill registry, memory, learning modules, then enters the main loop.
# -----------------------------

import threading
import time
import logging

from jarvis.config import Config
from jarvis.interfaces.voice_interface import VoiceInterface
from jarvis.interfaces.terminal_interface import TerminalInterface
from jarvis.nlu.intent_recognizer import IntentRecognizer
from jarvis.nlu.dialogue_manager import DialogueManager
from jarvis.memory.short_term import ShortTermMemory
from jarvis.memory.long_term import LongTermMemory
from jarvis.memory.vector_store import VectorStore
from jarvis.learning.reinforcement import ReinforcementAgent
from jarvis.utils.logger import get_logger

logger = get_logger(__name__)

class JarvisAssistant:
    def __init__(self, enable_voice: bool = True, enable_terminal: bool = True):
        # Load configuration
        self.cfg = Config()
        logger.info("Loaded configuration.")

        # Initialize persistent memory
        self.ltm = LongTermMemory(
            self.cfg.get("assistant", "memory", "long_term_db_path")
        )
        self.stm = ShortTermMemory(
            capacity=self.cfg.get("assistant", "memory", "short_term_capacity")
        )
        self.vector_store = VectorStore(
            self.cfg.get("assistant", "memory", "vector_store_path")
        )
        logger.info("Memory modules initialized.")

        # Initialize NLU components
        self.intent_recognizer = IntentRecognizer()
        self.dialogue_manager = DialogueManager()
        logger.info("NLU modules initialized.")

        # Initialize skill registry (mapping intents to handler functions)
        self.skill_registry = self._load_skills()
        logger.info("Skill registry created with %d skills.", len(self.skill_registry))

        # Initialize learning agent (RL) for proactive suggestions
        self.rl_agent = ReinforcementAgent(model_path="models/rl_policy_final.zip")
        logger.info("Reinforcement learning agent loaded.")

        # Initialize user interfaces conditionally
        self.voice_interface = None
        if enable_voice:
            self.voice_interface = VoiceInterface(callback=self._handle_input)
        self.terminal_interface = None
        if enable_terminal:
            self.terminal_interface = TerminalInterface(callback=self._handle_input)
        logger.info("User interfaces initialized.")

        self.running = False

    def _load_skills(self):
        """
        Dynamically import and register skill handlers.  
        Each skill module must expose:
            can_handle(intent: str) -> bool
            handle(intent: str, params: dict, context: dict) -> str
        """
        from jarvis.skills import (
            file_manager,
            scheduler,
            coding_helper,
            smart_home,
            info_query,
            conversation,
        )

        # Example registry: list of skill modules
        return [
            file_manager,
            scheduler,
            coding_helper,
            smart_home,
            info_query,
            conversation,
        ]

    def process_input(self, raw_text: str, source: str = "chat") -> str:
        """Process input text and return a response string."""
        logger.debug("Input received [%s]: %s", source, raw_text)
        intent, entities = self.intent_recognizer.parse(raw_text)
        context = self.stm.get_context()
        intent, entities = self.dialogue_manager.resolve_follow_up(intent, entities, context)
        entities["text"] = raw_text
        context["related_turns"] = self.vector_store.retrieve(raw_text)
        response = self._dispatch_intent(intent, entities, context)
        self.stm.append(turn={"input": raw_text, "intent": intent, "entities": entities, "response": response})
        self.vector_store.store(raw_text)
        self.rl_agent.observe(turn=self.stm.get_recent_turns(), memory=self.ltm)
        return response

    def _handle_input(self, raw_text: str, source: str = "voice"):
        """
        Common handler for both voice and terminal inputs.
        1. Pass raw_text to NLU to get (intent, entities).
        2. Pass intent/entities + STM/LTM to dialogue_manager to update context.
        3. Look up appropriate skill in skill_registry.
        4. Execute skill.handle() → gets a response string.
        5. Append to STM; emit response via TTS and/or print to terminal.
        """
        response = self.process_input(raw_text, source)
        if self.voice_interface:
            self.voice_interface.speak(response)
        if self.terminal_interface:
            self.terminal_interface.print(response)

    def _dispatch_intent(self, intent: str, params: dict, context: dict) -> str:
        """
        Find the first skill module whose can_handle(intent) returns True,
        then call its handle() method.
        If no skill can handle it, return a fallback message.
        """
        # Pass recent conversation turns so skills can leverage short term memory
        ctx = dict(context) if context else {}
        ctx["recent_turns"] = self.stm.get_recent_turns()
        if context and "related_turns" in context:
            ctx["related_turns"] = context["related_turns"]

        for skill in self.skill_registry:
            if skill.can_handle(intent):
                return skill.handle(intent, params, ctx)
        logger.warning("No skill found to handle intent '%s'", intent)
        return "Sorry, I didn’t understand that. Can you rephrase?"

    def start(self):
        """Start both interfaces and set running=True."""
        self.running = True
        logger.info("Starting Jarvis assistant...")

        # Start voice interface listening loop in a separate thread
        if self.voice_interface:
            voice_thread = threading.Thread(target=self.voice_interface.listen_loop, daemon=True)
            voice_thread.start()

        # Start terminal interface listening loop in a separate thread
        if self.terminal_interface:
            term_thread = threading.Thread(target=self.terminal_interface.listen_loop, daemon=True)
            term_thread.start()

        # Keep the main thread alive while interfaces run
        try:
            while self.running:
                time.sleep(0.5)
        except KeyboardInterrupt:
            logger.info("Shutdown requested by user (KeyboardInterrupt).")
            self.shutdown()

    def shutdown(self):
        """Cleanly stop all loops and perform any cleanup."""
        self.running = False
        if self.voice_interface:
            self.voice_interface.stop()
        if self.terminal_interface:
            self.terminal_interface.stop()
        logger.info("Jarvis assistant shut down.")


if __name__ == "__main__":
    assistant = JarvisAssistant()
    assistant.start()
