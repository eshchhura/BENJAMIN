"""jarvis/nlu/intent_recognizer.py
---------------------------------
Simple intent recognition and entity extraction using spaCy.
This replaces the previous Rasa based implementation which is
incompatible with Python 3.11.
"""

from __future__ import annotations

import logging
import re
from typing import Dict, Tuple

import spacy

logger = logging.getLogger(__name__)


class IntentRecognizer:
    """Lightweight rule based intent recognizer backed by spaCy NER."""

    def __init__(self, model_name: str = "en_core_web_sm") -> None:
        try:
            self.nlp = spacy.load(model_name)
        except OSError:
            # Model isn't installed - download it on the fly
            from spacy.cli import download

            logger.info("Downloading spaCy model %s", model_name)
            download(model_name)
            self.nlp = spacy.load(model_name)

        # Precompiled regex patterns mapping to intents
        self.patterns: list[tuple[re.Pattern[str], str]] = [
            (re.compile(r"open file (?P<file_name>.+)", re.I), "open_file"),
            (re.compile(r"(?:find|search for) (?P<query>.+)", re.I), "search_file"),
            (
                re.compile(
                    r"move file (?P<source>\S+) to (?P<destination>.+)", re.I
                ),
                "move_file",
            ),
            (
                re.compile(
                    r"remind me to (?P<message>.+?) (?:at|on) (?P<datetime>.+)",
                    re.I,
                ),
                "create_reminder",
            ),
            (re.compile(r"list reminders", re.I), "list_reminders"),
            (re.compile(r"delete reminder (?P<id>\d+)", re.I), "delete_reminder"),
            (
                re.compile(r"weather (?:in|for) (?P<location>.+)", re.I),
                "weather_query",
            ),
            (re.compile(r"news about (?P<topic>.+)", re.I), "news_query"),
            (re.compile(r"define (?P<term>.+)", re.I), "define_term"),
            (re.compile(r"explain (?P<error_message>.+)", re.I), "explain_error"),
            (
                re.compile(r"generate code for (?P<task>.+)", re.I),
                "generate_code",
            ),
            (
                re.compile(r"stackoverflow (?P<question>.+)", re.I),
                "search_stackoverflow",
            ),
        ]

    def parse(self, text: str) -> Tuple[str, Dict[str, str]]:
        """Return (intent, entities) for the supplied text."""
        intent = "unknown"
        entities: Dict[str, str] = {}

        for pattern, name in self.patterns:
            match = pattern.search(text)
            if match:
                intent = name
                entities.update({k: v.strip() for k, v in match.groupdict().items()})
                break

        doc = self.nlp(text)
        for ent in doc.ents:
            # Only add entity if not already present
            entities.setdefault(ent.label_.lower(), ent.text)

        logger.debug("Parsed intent %s with entities %s", intent, entities)
        return intent, entities

