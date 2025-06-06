# jarvis/memory/short_term.py
# -----------------------------------
# Keeps the last N turns of conversation in RAM.
# -----------------------------------

from collections import deque

class ShortTermMemory:
    """
    FIFO queue of the most recent conversation turns.
    Each turn is a dict: {'input': str, 'intent': str, 'entities': dict, 'response': str}.
    """

    def __init__(self, capacity: int = 50):
        self.capacity = capacity
        self.turns = deque(maxlen=capacity)

    def append(self, turn: dict):
        """
        Add a new turn to STM (automatically drops oldest if over capacity).
        """
        self.turns.append(turn)

    def get_recent_turns(self):
        """
        Return a list of recent turns (newest last).
        """
        return list(self.turns)

    def get_context(self):
        """
        Provide summarized context for NLU (e.g., last intent/entities).
        For now, return a simple mapping:
        {'last_intent': ..., 'last_entities': ...}
        """
        if not self.turns:
            return {}
        last = self.turns[-1]
        return {'last_intent': last.get('intent'), 'last_entities': last.get('entities')}
