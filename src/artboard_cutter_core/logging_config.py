from __future__ import annotations

import json
import logging
import tempfile
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from .settings import default_log_dir


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(timespec="seconds"),
            "level": record.levelname,
            "module": record.name,
            "message": record.getMessage(),
        }
        extra = getattr(record, "extra_data", None)
        if isinstance(extra, dict):
            payload.update(extra)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def get_logger(name: str, log_dir: Path | str | None = None, filename: str = "app.log") -> logging.Logger:
    logger = logging.getLogger(f"artboard_cutter.{name}")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False

    preferred_path = Path(log_dir) if log_dir is not None else default_log_dir()
    fallback_path = Path(tempfile.gettempdir()) / "ArtboardCutter" / "logs"
    handler = None
    last_error = None
    for log_path in dict.fromkeys((preferred_path, fallback_path)):
        try:
            log_path.mkdir(parents=True, exist_ok=True)
            handler = RotatingFileHandler(
                log_path / filename,
                maxBytes=1_000_000,
                backupCount=5,
                encoding="utf-8",
            )
            break
        except OSError as exc:
            last_error = exc
    if handler is None:
        raise last_error or OSError("Could not create an Artboard Cutter log file.")
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    return logger


def log_event(logger: logging.Logger | None, level: int, action: str, **extra_data) -> None:
    if logger is None:
        return
    logger.log(level, action, extra={"extra_data": {"action": action, **extra_data}})
