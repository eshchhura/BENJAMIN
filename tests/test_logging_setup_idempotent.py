from __future__ import annotations

import logging

from benjamin.core.logging.setup import configure_logging


def test_configure_logging_is_idempotent(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BENJAMIN_LOG_TO_FILE", "off")

    logger = logging.getLogger("benjamin")
    logger.handlers = []

    configure_logging(tmp_path)
    first_count = len(logger.handlers)

    configure_logging(tmp_path)
    assert len(logger.handlers) == first_count
