# jarvis/utils/logger.py
# -----------------------------------
# Provides a centralized logger factory that reads config/logging.yaml
# -----------------------------------

import logging

def get_logger(name: str) -> logging.Logger:
    """
    Returns a named logger using configuration loaded in jarvis/config.py.
    """
    return logging.getLogger(f"jarvis.{name}")
