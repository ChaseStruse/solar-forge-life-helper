"""Backups must be consistent, verifiable copies of the live family database."""

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from solar_forge_desktop.backups import (
    create_backup,
    latest_backup,
    next_backup_due,
    prune_backups,
    verify_backup,
)
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


def test_due_time_and_retention_keep_newest_verified_copies(tmp_path: Path) -> None:
    database = tmp_path / "data" / DATABASE_NAME
    storage = Storage(database)
    folder = tmp_path / "backups"
    first = create_backup(database, folder)
    storage.create_profile("Family")
    second = create_backup(database, folder)
    third = create_backup(database, folder)
    storage.close()

    now = datetime.now(timezone.utc)
    assert next_backup_due(folder, "off", now) is None
    assert next_backup_due(folder, "daily", now) > now
    assert next_backup_due(folder, "weekly", now) > now + timedelta(days=6)
    assert prune_backups(folder, 2) == 1
    assert not first.database.exists()
    assert verify_backup(second.manifest) == second
    assert verify_backup(third.manifest) == third


def test_retention_does_not_delete_corrupt_backup(tmp_path: Path) -> None:
    database = tmp_path / "data" / DATABASE_NAME
    storage = Storage(database)
    storage.close()
    folder = tmp_path / "backups"
    damaged = create_backup(database, folder)
    damaged.database.write_bytes(b"damaged")
    healthy = create_backup(database, folder)

    assert prune_backups(folder, 1) == 0
    assert damaged.database.exists()
    assert verify_backup(healthy.manifest) == healthy
