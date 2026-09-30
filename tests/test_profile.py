"""Profile settings ownership, persistence, validation, and v13 migration."""

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from solar_forge_desktop.profile import ProfileService
from solar_forge_desktop.storage import Storage


def test_profile_defaults_update_ownership_and_restart(tmp_path: Path) -> None:
    path = tmp_path / "solar-forge.db"
    storage = Storage(path)
    first = storage.default_profile_id()
    second = storage.create_profile("Other")
    service = ProfileService(storage)
    assert service.view(first).avatar_emoji == "🌙"
    assert service.view(first).quick_access_apps[-1] == "meals"
    updated = service.update(first, " Alex ", " A calmer day ", "#ec4899", "🚀")
    assert (updated.name, updated.bio, updated.avatar_color, updated.avatar_emoji) == (
        "Alex", "A calmer day", "#ec4899", "🚀"
    )
    assert service.view(second).name == "Other"
    storage.close()
    reopened = Storage(path)
    assert ProfileService(reopened).view(first) == updated
    assert ProfileService(reopened).view(second).avatar_color == "#8b5cf6"
    reopened.close()


def test_profile_validation_and_color_icon_fallback(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "solar-forge.db")
    service = ProfileService(storage)
    first = storage.default_profile_id()
    for args, message in (
        ((" ", "", "#8b5cf6", "🌙"), "Name cannot"),
        ((("x" * 101), "", "#8b5cf6", "🌙"), "100 characters"),
        (("Alex", "x" * 2001, "#8b5cf6", "🌙"), "Bio must"),
    ):
        with pytest.raises(ValueError, match=message):
            service.update(first, *args)
    fallback = service.update(first, "Alex", "", "red;evil", "overlong")
    assert (fallback.avatar_color, fallback.avatar_emoji) == ("#8b5cf6", "🌙")
    with pytest.raises(ValueError, match="Profile not found"):
        service.view(999)
    with pytest.raises(ValueError, match="Profile not found"):
        service.update(999, "Alex", "", "#8b5cf6", "🌙")
    storage.close()


def test_v13_upgrade_snapshot_and_missing_settings(tmp_path: Path) -> None:
    path = tmp_path / "old.db"
    storage = Storage(path)
    storage.close()
    with closing(sqlite3.connect(path)) as db:
        db.execute("DROP TABLE profile_settings")
        db.execute("PRAGMA user_version=13")
        db.commit()
    upgraded = Storage(path)
    assert ProfileService(upgraded).view(upgraded.default_profile_id()).name == "Home"
    upgraded.close()
    with closing(sqlite3.connect(path.with_name("old.db.pre-profile-v13"))) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 13
        assert "profile_settings" not in {
            row[0] for row in db.execute("SELECT name FROM sqlite_master")
        }
    with closing(sqlite3.connect(path)) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 15
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        db.execute("DROP TABLE profile_settings")
        db.commit()
    with pytest.raises(RuntimeError, match="missing profile settings"):
        Storage(path)
