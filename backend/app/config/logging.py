import logging
import sys

from app.config.formatter import KeyValueFormatter


def configure_logging(level: str = "INFO") -> None:
    """Configure root logging with the structured key-value formatter."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(KeyValueFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
