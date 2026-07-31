from __future__ import annotations

import logging
from pathlib import Path


def configure_logging(log_dir: str | Path = "logs") -> Path:
    path = Path(log_dir)
    path.mkdir(parents=True, exist_ok=True)
    file_path = path / "customer-service.log"

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    if not any(isinstance(h, logging.FileHandler) for h in logger.handlers):
        handler = logging.FileHandler(file_path, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
        logger.addHandler(handler)

    return file_path
