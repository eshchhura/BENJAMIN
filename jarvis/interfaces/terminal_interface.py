# jarvis/interfaces/terminal_interface.py
# ---------------------------------------
# Reads text input from the terminal in a loop and passes it to callback.
# Also provides a print() wrapper to ensure consistent formatting.
# ---------------------------------------

import threading
import sys
import logging

logger = logging.getLogger(__name__)

class TerminalInterface:
    """
    - Runs a loop waiting for user to type commands (no wake-word required).
    - On each line entered, invokes callback(text, source="terminal").
    - print() simply prefixes text with “[Benjamin]: ”.
    """

    def __init__(self, callback):
        self.callback = callback
        self.running = False

    def listen_loop(self):
        """
        Blocks on input() until newline; sends to callback.
        """
        self.running = True
        logger.info("TerminalInterface ready for commands. Type 'exit' to quit.")
        while self.running:
            try:
                user_input = input(">>> ").strip()
            except (EOFError, KeyboardInterrupt):
                # Graceful shutdown on Ctrl+C or Ctrl+D
                logger.info("TerminalInterface received shutdown signal.")
                self.running = False
                break

            if user_input.lower() in {"exit", "quit"}:
                logger.info("User requested exit via terminal.")
                self.running = False
                # Let the assistant’s main loop handle full shutdown
                break

            if user_input:
                self.callback(user_input, source="terminal")

    def print(self, text: str):
        """
        Print assistant responses to the terminal (prefix with [Benjamin]).
        """
        print(f"[Benjamin]: {text}")

    def stop(self):
        self.running = False
