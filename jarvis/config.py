# jarvis/config.py
# -----------------------------
# Loads and exposes configuration from config/config.yaml
# -----------------------------

import os
import logging
import logging.config
from typing import Any, Optional
import yaml

from config.loader import JarvisConfig, load_config

class Config:
    """Singleton configuration loader."""
    _instance = None

    def __new__(cls, config_path=None):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance._load(config_path)
        return cls._instance

    def _load(self, config_path: Optional[str] = None) -> None:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        default_path = os.path.join(base, "config", "config.yaml")
        path = config_path or default_path

        self._data: JarvisConfig = load_config(path)

        log_cfg = self._data.logging
        if log_cfg.config_file and os.path.exists(log_cfg.config_file):
            with open(log_cfg.config_file, "r") as f:
                logging.config.dictConfig(yaml.safe_load(f))
        else:
            logging.basicConfig(level=getattr(logging, log_cfg.level, logging.INFO))

    def get(self, *keys, default=None):
        """
        Retrieve a nested configuration value, e.g. config.get('assistant', 'name').
        """
        data: Any = self._data
        for key in keys:
            if hasattr(data, key):
                data = getattr(data, key)
            elif isinstance(data, dict) and key in data:
                data = data[key]
            else:
                return default
        return data

# Usage:
# from jarvis.config import Config
# cfg = Config()
# assistant_name = cfg.get("assistant", "name")
