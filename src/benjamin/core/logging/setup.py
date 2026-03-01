from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .json_formatter import JSONFormatter

_LOGGER_NAME = "benjamin"
_CONFIGURED_ATTR = "_benjamin_json_logging"


def _parse_level(raw: str) -> int:
    normalized = raw.strip().upper()
    return getattr(logging, normalized, logging.INFO)


def _is_on(name: str, default: str = "on") -> bool:
    return os.getenv(name, default).strip().casefold() == "on"


def configure_logging(state_dir: Path) -> logging.Logger:
    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(_parse_level(os.getenv("BENJAMIN_LOG_LEVEL", "INFO")))
    logger.propagate = False

    formatter = JSONFormatter()

    if not any(getattr(handler, _CONFIGURED_ATTR, False) for handler in logger.handlers):
        stdout_handler = logging.StreamHandler(stream=sys.stdout)
        stdout_handler.setFormatter(formatter)
        setattr(stdout_handler, _CONFIGURED_ATTR, True)
        logger.addHandler(stdout_handler)

    if _is_on("BENJAMIN_LOG_TO_FILE", "on"):
        log_dir = Path(os.getenv("BENJAMIN_LOG_DIR") or (state_dir / "logs"))
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "benjamin.log"
        max_bytes = int(os.getenv("BENJAMIN_LOG_MAX_BYTES", "5000000"))
        backup_count = int(os.getenv("BENJAMIN_LOG_BACKUP_COUNT", "5"))

        file_exists = any(
            isinstance(handler, RotatingFileHandler)
            and getattr(handler, _CONFIGURED_ATTR, False)
            and Path(handler.baseFilename) == log_path
            for handler in logger.handlers
        )
        if not file_exists:
            file_handler = RotatingFileHandler(
                filename=log_path,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)
            setattr(file_handler, _CONFIGURED_ATTR, True)
            logger.addHandler(file_handler)

    return logger
