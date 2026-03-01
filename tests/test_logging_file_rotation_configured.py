from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from benjamin.core.logging.setup import configure_logging


def test_logging_file_rotation_handler_configured(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BENJAMIN_LOG_TO_FILE", "on")
    monkeypatch.setenv("BENJAMIN_LOG_DIR", str(tmp_path / "custom-logs"))

    logger = logging.getLogger("benjamin")
    logger.handlers = []

    configure_logging(tmp_path / "state")

    handlers = [h for h in logger.handlers if isinstance(h, RotatingFileHandler)]
    assert handlers
    assert (tmp_path / "custom-logs").exists()


def test_logging_creates_state_log_dir_when_missing(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BENJAMIN_LOG_TO_FILE", "on")
    monkeypatch.delenv("BENJAMIN_LOG_DIR", raising=False)

    logger = logging.getLogger("benjamin")
    logger.handlers = []

    state_dir = tmp_path / "missing-state"
    configure_logging(state_dir)

    assert (state_dir / "logs").exists()
