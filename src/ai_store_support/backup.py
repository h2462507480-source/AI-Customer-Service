from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path


def backup_database(source: str | Path, target_dir: str | Path) -> Path:
    """Create a timestamped SQLite backup copy."""
    source_path = Path(source)
    directory = Path(target_dir)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = directory / f"ai-store-support-{stamp}.db"
    shutil.copy2(source_path, target)
    return target


def export_json(data: object, target: str | Path) -> Path:
    """Export admin snapshots and operation records."""
    path = Path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path
