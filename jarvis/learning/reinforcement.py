# jarvis/learning/reinforcement.py
# -----------------------------------
# Wraps an RL policy (trained offline) to decide whether Benjamin should proactively interject.
# For example, “You have a meeting in 15 minutes—should I remind you now?”
# -----------------------------------

import logging
import numpy as np

try:
    from stable_baselines3 import PPO
except Exception as e:  # pragma: no cover - optional dependency
    PPO = None
    logging.getLogger(__name__).warning(
        "stable-baselines3 not available: %s", e
    )

logger = logging.getLogger(__name__)

class ReinforcementAgent:
    """
    Loads a pretrained RL model (PPO, DQN, etc.).  
    At each new turn or time interval, it observes state features (time, context, user activity)
    and outputs an action. If action==‘suggest_reminder’, main loop issues a proactive prompt.
    """

    def __init__(self, model_path: str):
        if PPO is None:
            logger.warning("Reinforcement learning disabled: stable-baselines3 not installed")
            self.model = None
            return
        try:
            self.model = PPO.load(model_path)
            logger.info("ReinforcementAgent loaded model from %s.", model_path)
        except Exception as e:
            logger.warning("Could not load RL model: %s", e)
            self.model = None

    def observe(self, turn: list, memory, **kwargs):
        """
        Given recent turns and long_term memory, build a state vector.
        Example features: time_of_day, day_of_week, last_intent_id, number_of_pending_reminders.
        Then call self.model.predict(state) to get an action.
        If action maps to a suggestion, return that suggestion or trigger it via callback.
        """
        if not self.model:
            return
        # Build dummy state (replace with real features):
        state = np.zeros(10, dtype=np.float32)
        action, _ = self.model.predict(state, deterministic=True)
        # Example: action==1 means “suggest reminder now”
        if action == 1:
            # Decide what to suggest (e.g., based on pending reminders in memory)
            suggestion = "You have a meeting in 10 minutes. Should I remind you now?"
            # Ideally return suggestion to main loop to speak/print
            logger.info("RL suggests: %s", suggestion)
            # In practice, main loop might register callback for proactive messages
            return suggestion
        return None
