from __future__ import annotations

import io
import json
import logging

from benjamin.core.logging.context import log_context
from benjamin.core.logging.json_formatter import JSONFormatter


def test_logging_json_line_with_context() -> None:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JSONFormatter())

    logger = logging.getLogger("benjamin.test.json")
    logger.handlers = []
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.addHandler(handler)

    with log_context(correlation_id="c1", task_id="t1"):
        logger.info("hello")

    payload = json.loads(stream.getvalue().strip())
    assert payload["msg"] == "hello"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "benjamin.test.json"
    assert payload["correlation_id"] == "c1"
    assert payload["task_id"] == "t1"
    assert "ts_iso_utc" in payload
