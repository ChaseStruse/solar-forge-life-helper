"""Calendar reminder rules remain private and deduplicate local delivery."""

import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import pytest

from solar_forge_desktop.calendar import CalendarService
from solar_forge_desktop.reminders import CalendarReminderService
from solar_forge_desktop.storage import Storage


def test_v15_upgrade_adds_reminders_without_changing_events(tmp_path: Path) -> None:
    path = tmp_path / "family.db"
    storage = Storage(path)
    owner = storage.default_profile_id()
    event_id = CalendarService(storage).save(
        owner, "Keep this", None, "Home", datetime(2026, 11, 1, 9),
        datetime(2026, 11, 1, 10),
    )
    storage.close()
    with closing(sqlite3.connect(path)) as db:
        db.execute("DROP TABLE calendar_reminder_deliveries")
        db.execute("DROP TABLE calendar_reminders")
        db.execute("PRAGMA user_version=15")
        db.commit()
    upgraded = Storage(path)
    assert CalendarService(upgraded).get(owner, event_id).title == "Keep this"
    upgraded.close()
    with closing(sqlite3.connect(path)) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 16
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    with closing(sqlite3.connect(path.with_name("family.db.pre-reminders-v15"))) as snapshot:
        assert snapshot.execute("PRAGMA user_version").fetchone()[0] == 15


def test_due_recurring_event_deduplicates_and_honors_household(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "family.db")
    owner = storage.default_profile_id()
    member = storage.create_profile("Member")
    calendar = CalendarService(storage)
    event_id = calendar.save(
        owner, "Family dinner", None, "Family", datetime(2026, 10, 1, 18),
        datetime(2026, 10, 1, 19), recurrence="daily", visibility="household",
    )
    reminders = CalendarReminderService(storage)
    reminders.set_rule(member, event_id, 30, "America/Chicago")
    now = datetime(2026, 10, 1, 22, 35, tzinfo=timezone.utc)
    due = reminders.due(member, now)
    assert len(due) == 1
    assert due[0].title == "Family dinner"
    assert due[0].due_at.astimezone(timezone.utc) == datetime(
        2026, 10, 1, 22, 30, tzinfo=timezone.utc
    )
    assert reminders.mark_delivered(member, due[0], now)
    assert reminders.due(member, now) == ()
    assert not reminders.mark_delivered(member, due[0], now)
    next_day = datetime(2026, 10, 2, 22, 35, tzinfo=timezone.utc)
    assert len(reminders.due(member, next_day)) == 1
    calendar.save(owner, "Private dinner", None, "Family", datetime(2026, 10, 1, 18),
                  datetime(2026, 10, 1, 19), event_id=event_id, visibility="private")
    assert reminders.due(member, next_day) == ()
    storage.close()


def test_reminders_validate_time_zone_and_skip_dst_gap(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "family.db")
    owner = storage.default_profile_id()
    calendar = CalendarService(storage)
    event_id = calendar.save(
        owner, "Early check", None, "Home", datetime(2026, 3, 7, 2, 30),
        datetime(2026, 3, 7, 3, 30), recurrence="daily",
    )
    reminders = CalendarReminderService(storage)
    with pytest.raises(ValueError, match="time zone"):
        reminders.set_rule(owner, event_id, 0, "Invalid/TimeZone")
    with pytest.raises(ValueError, match="lead time"):
        reminders.set_rule(owner, event_id, 45, "America/Chicago")
    reminders.set_rule(owner, event_id, 0, "America/Chicago")
    march_8 = datetime(2026, 3, 8, 9, 0, tzinfo=timezone.utc)
    assert reminders.due(owner, march_8) == ()
    storage.close()
