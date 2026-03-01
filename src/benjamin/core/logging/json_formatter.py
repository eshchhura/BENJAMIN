from __future__ import annotations

import json
import logging
import traceback
from datetime import datetime, timezone

from .context import get_log_context


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts_iso_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        payload.update(get_log_context())

        extra_fields = getattr(record, "extra_fields", None)
        if isinstance(extra_fields, dict):
            payload.update(extra_fields)

        if record.exc_info:
            exc_type, exc_value, exc_tb = record.exc_info
            payload["exc_type"] = exc_type.__name__ if exc_type else "Exception"
            payload["exc_msg"] = str(exc_value) if exc_value else ""
            payload["stack"] = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))

        return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
