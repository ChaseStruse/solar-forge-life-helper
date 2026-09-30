"""Backups must be consistent, verifiable copies of the live family database."""

import json
import sqlite3
from pathlib import Path

import pytest

from solar_forge_desktop.backups import create_backup, latest_backup, verify_backup
from solar_forge_desktop.configuration import DATABASE_NAME
from solar_forge_desktop.storage import Storage


def test_backup_live_database_has_manifest_and_original_is_untouched(tmp_path: Path) -> None:
    database = tmp_path / "data" / DATABASE_NAME
    storage = Storage(database)
    profile_id = storage.create_profile("Family")
    backup_folder = tmp_path / "backups"

    info = create_backup(database, backup_folder)

    assert latest_backup(backup_folder) == info.manifest
    assert verify_backup(info.manifest) == info
    document = json.loads(info.manifest.read_text())
    assert document["database_file"] == info.database.name
    assert document["app_version"]
    with sqlite3.connect(info.database) as snapshot:
        assert snapshot.execute("PRAGMA user_version").fetchone()[0] == 14
        row = snapshot.execute("SELECT name FROM profiles WHERE id=?", (profile_id,)).fetchone()
        assert row == ("Family",)
    assert storage.profile_name(profile_id) == "Family"
    storage.close()


def test_corrupted_backup_fails_verification(tmp_path: Path) -> None:
    database = tmp_path / "data" / DATABASE_NAME
    storage = Storage(database)
    storage.close()
    info = create_backup(database, tmp_path / "backups")
    info.database.write_bytes(b"corrupted")

    with pytest.raises(ValueError, match="does not match"):
        verify_backup(info.manifest)
    assert database.is_file()


def test_failed_backup_leaves_no_published_file(tmp_path: Path) -> None:
    database = tmp_path / "data" / DATABASE_NAME
    database.parent.mkdir()
    database.write_bytes(b"not a database")
    backup_folder = tmp_path / "backups"

    with pytest.raises(sqlite3.DatabaseError):
        create_backup(database, backup_folder)
    assert list(backup_folder.iterdir()) == []
    assert database.read_bytes() == b"not a database"


def test_backup_folder_must_be_separate(tmp_path: Path) -> None:
    database = tmp_path / "data" / DATABASE_NAME
    storage = Storage(database)
    storage.close()
    with pytest.raises(ValueError, match="separate"):
        create_backup(database, database.parent)
