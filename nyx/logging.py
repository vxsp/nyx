"""Small rotating JSON logs. Never log server bodies or raw exceptions."""
from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import re


def redact(text: str) -> str:
    for key, value in os.environ.items():
        if value and re.search(r"PASSWORD|TOKEN|SECRET|API_KEY", key, re.I):
            text = text.replace(value, "[redacted]")
    text = re.sub(r"https?://\S+", "[URL withheld]", text)
    return text


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({
            "at": self.formatTime(record), "level": record.levelname,
            "message": redact(record.getMessage()),
        })


def configure_logging(root: Path) -> logging.Logger:
    logger = logging.getLogger("nyx")
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)
    path = root / "logs" / "nyx.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(path, maxBytes=256 * 1024, backupCount=2, encoding="utf-8")
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger
