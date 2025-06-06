# jarvis/config.py
# -----------------------------
# Loads and exposes configuration from config/config.yaml
# -----------------------------

import os
import yaml
import logging.config

class Config:
    """Singleton configuration loader."""
    _instance = None

    def __new__(cls, config_path=None):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance._load(config_path)
        return cls._instance

    def _load(self, config_path=None):
        # Default to 'config/config.yaml' at repo root
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        default_path = os.path.join(base, "config", "config.yaml")
        path = config_path or default_path
        with open(path, "r") as f:
            config_data = yaml.safe_load(f)
        self._data = config_data

        # Setup logging immediately
        log_cfg = self._data.get("logging", {})
        if log_cfg and os.path.exists(log_cfg.get("config_file", "")):
            logging.config.dictConfig(log_cfg)
        else:
            # Fallback: basicConfig
            import logging
            logging.basicConfig(level=logging.INFO)

    def get(self, *keys, default=None):
        """
        Retrieve a nested configuration value, e.g. config.get('assistant', 'name').
        """
        data = self._data
        for key in keys:
            if data and key in data:
                data = data[key]
            else:
                return default
        return data

# Usage:
# from jarvis.config import Config
# cfg = Config()
# assistant_name = cfg.get("assistant", "name")
