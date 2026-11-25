import json
import logging
from datetime import UTC, datetime


class KeyValueFormatter(logging.Formatter):
    """Structured single-line log formatter: ts, level, logger, message and extra fields."""

    _RESERVED = frozenset({"name", "msg", "args", "levelname", "levelno", "pathname", "filename", "module", "exc_info",
                           "exc_text", "stack_info", "lineno", "funcName", "created", "msecs", "relativeCreated",
                           "thread", "threadName", "processName", "process", "taskName", "message", "asctime"})

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in self._RESERVED and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)
