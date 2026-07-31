from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_logging(
    log_dir: str | Path = "logs",
    *,
    max_bytes: int = 5 * 1024 * 1024,
    backup_count: int = 5,
) -> Path:
    path = Path(log_dir)
    path.mkdir(parents=True, exist_ok=True)
    file_path = (path / "customer-service.log").resolve()

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    for handler in list(logger.handlers):
        if getattr(handler, "_ai_store_support_handler", False):
            if Path(getattr(handler, "baseFilename", "")).resolve() == file_path:
                return file_path
            logger.removeHandler(handler)
            handler.close()

    handler = RotatingFileHandler(
        file_path,
        maxBytes=max(1024, int(max_bytes)),
        backupCount=max(1, int(backup_count)),
        encoding="utf-8",
    )
    handler._ai_store_support_handler = True  # type: ignore[attr-defined]
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
    logger.addHandler(handler)
    return file_path
