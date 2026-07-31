from pathlib import Path

from ai_store_support.backup import backup_database, export_json


def test_backup_and_export(tmp_path: Path):
    db = tmp_path / "source.db"
    db.write_text("demo", encoding="utf-8")

    backup = backup_database(db, tmp_path / "backups")
    assert backup.exists()
    assert backup.read_text(encoding="utf-8") == "demo"

    exported = export_json({"ok": True}, tmp_path / "export" / "data.json")
    assert exported.exists()
    assert "true" in exported.read_text(encoding="utf-8")
