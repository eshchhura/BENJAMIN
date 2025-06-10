from __future__ import annotations

"""Configuration loader for Benjamin assistant."""

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field, validator


class MemorySettings(BaseModel):
    short_term_capacity: int = 50
    long_term_db_path: str
    vector_store_path: str


class AssistantSettings(BaseModel):
    name: str = "Benjamin"
    language: str = "en"
    wake_word: str = Field("hey benjamin", alias="wake_word")
    stt_engine: str = "vosk"
    tts_engine: str = "pyttsx3"
    nlu_engine: str = "spacy"
    memory: MemorySettings


class APIKeys(BaseModel):
    google_calendar: Optional[str] = None
    openai: Optional[str] = None
    weather: Optional[str] = None


class HomeAssistantConfig(BaseModel):
    host: str = "http://localhost:8123"
    access_token: Optional[str] = None


class LoggingConfig(BaseModel):
    level: str = "INFO"
    config_file: Optional[str] = None


class BenjaminConfig(BaseModel):
    assistant: AssistantSettings
    api_keys: APIKeys = Field(default_factory=APIKeys)
    home_assistant: HomeAssistantConfig = Field(default_factory=HomeAssistantConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


_DEF_PATH = Path(__file__).resolve().parent / "config.yaml"


def load_config(path: Optional[str] = None) -> BenjaminConfig:
    """Load and validate configuration from YAML file."""
    cfg_path = Path(path) if path else _DEF_PATH
    with cfg_path.open("r") as f:
        data = yaml.safe_load(f) or {}
    return BenjaminConfig.parse_obj(data)
