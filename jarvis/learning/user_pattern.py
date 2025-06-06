# jarvis/learning/user_pattern.py
# -----------------------------------
# Mines the ShortTermMemory/interactions log to identify frequent command patterns.
# For example, every weekday at 8 AM the user asks “open VSCode”.  
# Suggest automating it.
# -----------------------------------

import logging
from collections import Counter
from datetime import datetime

logger = logging.getLogger(__name__)

class UserPatternLearner:
    """
    Simple heuristics: 
    - Count how often each intent occurs at different hours/days.
    - Identify top intents with high frequency in a given context.
    """
    def __init__(self, stm, ltm):
        self.stm = stm
        self.ltm = ltm

    def extract_patterns(self):
        """
        Example: 
        - For each turn in LTM interaction_log, bucket by (intent, hour_of_day).
        - Find (intent, hour) pairs with count above a threshold.
        """
        # Pseudocode: fetch interaction_log from LTM, parse timestamps.
        # Build Counter of (intent, weekday, hour).
        pass

    def suggest_automation(self):
        """
        Based on extracted patterns, return suggestions like:
        “You often open VSCode around 9 AM on weekdays—should I open it automatically?”
        """
        # Check if a pattern reaches a certain frequency. If so, return suggestion.
        return None
