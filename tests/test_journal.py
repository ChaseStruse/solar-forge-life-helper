"""Journal storage, ownership, validation, ordering, and schema upgrades."""

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from solar_forge_desktop.journal import JournalService
from solar_forge_desktop.storage import Storage


def test_journal_create_edit_delete_persists_and_is_profile_scoped(tmp_path: Path) -> None:
    path = tmp_path / "journal.db"
    storage = Storage(path)
    first = storage.default_profile_id()
    other = storage.create_profile("Other")
    journal = JournalService(storage)
    entry_id = journal.add_entry(first, "  First title  ", "  Line one\nLine two  ")
    saved = journal.list_entries(first)[0]
    assert (saved.id, saved.title, saved.content) == (entry_id, "First title", "Line one\nLine two")
    assert saved.created_at == saved.updated_at
    assert journal.list_entries(other) == ()
    for operation in (
        lambda: journal.edit_entry(other, entry_id, "Changed", "Other content"),
        lambda: journal.delete_entry(other, entry_id),
    ):
        with pytest.raises(ValueError, match="not found"):
            operation()
    journal.edit_entry(first, entry_id, "  Updated  ", " New content ")
    changed = journal.list_entries(first)[0]
    assert (changed.title, changed.content) == ("Updated", "New content")
    assert changed.created_at == saved.created_at
    assert changed.updated_at >= saved.updated_at
    storage.close()
    reopened = Storage(path)
    assert JournalService(reopened).list_entries(first)[0].content == "New content"
    JournalService(reopened).delete_entry(first, entry_id)
    assert JournalService(reopened).list_entries(first) == ()
    reopened.close()


def test_journal_validation_and_bounded_newest_first_history(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "journal.db")
    profile = storage.default_profile_id()
    journal = JournalService(storage)
    for title, content, message in (
        (" ", "content", "title is required"),
        ("x" * 201, "content", "200 characters"),
        ("Title", "  ", "content is required"),
    ):
        with pytest.raises(ValueError, match=message):
            journal.add_entry(profile, title, content)
    with pytest.raises(ValueError, match="Profile not found"):
        journal.list_entries(999)
    with pytest.raises(ValueError, match="Profile not found"):
        journal.add_entry(999, "Title", "Content")
    with pytest.raises(ValueError, match="limit"):
        journal.list_entries(profile, 0)
    with pytest.raises(ValueError, match="limit"):
        journal.list_entries(profile, 501)
    first = journal.add_entry(profile, "First", "One")
    second = journal.add_entry(profile, "Second", "Two")
    assert [item.id for item in journal.list_entries(profile, 1)] == [second]
    with pytest.raises(ValueError, match="title is required"):
        journal.edit_entry(profile, first, " ", "Valid")
    assert journal.list_entries(profile)[-1].title == "First"
    storage.close()


def test_v3_upgrade_snapshots_before_journal_schema(tmp_path: Path) -> None:
    path = tmp_path / "old.db"
    storage = Storage(path)
    profile = storage.default_profile_id()
    storage.close()
    with closing(sqlite3.connect(path)) as db:
        db.execute("DROP TABLE profile_settings")
        db.execute("DROP TABLE calendar_events")
        db.execute("DROP TABLE maintenance_items")
        db.execute("DROP TABLE favorite_meals")
        db.execute("DROP TABLE meal_plans")
        db.execute("DROP TABLE pet_care_records")
        db.execute("DROP TABLE pets")
        db.execute("DROP TABLE workout_logs")
        db.execute("DROP TABLE weight_logs")
        db.execute("DROP TABLE weight_goals")
        db.execute("DROP TABLE calorie_goals")
        db.execute("DROP TABLE food_logs")
        db.execute("DROP TABLE habit_checks")
        db.execute("DROP TABLE habits")
        db.execute("DROP TABLE medicine_logs")
        db.execute("DROP TABLE journal_entries")
        db.execute("PRAGMA user_version=3")
        db.commit()
    upgraded = Storage(path)
    assert JournalService(upgraded).list_entries(profile) == ()
    upgraded.close()
    with closing(sqlite3.connect(path.with_name("old.db.pre-journal-v3"))) as snapshot:
        assert snapshot.execute("PRAGMA user_version").fetchone()[0] == 3
        assert "journal_entries" not in {
            row[0] for row in snapshot.execute("SELECT name FROM sqlite_master")
        }
    with closing(sqlite3.connect(path)) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 16
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
