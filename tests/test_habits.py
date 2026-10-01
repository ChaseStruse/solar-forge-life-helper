"""Habit rules and versioned storage using disposable databases."""

import sqlite3
from contextlib import closing
from datetime import date
from pathlib import Path

import pytest

from solar_forge_desktop.habits import HabitService
from solar_forge_desktop.storage import Storage


def test_week_checks_isolation_cascade_and_restart(tmp_path: Path) -> None:
    path = tmp_path / "habits.db"
    storage = Storage(path)
    first = storage.default_profile_id()
    second = storage.create_profile("Other")
    habits = HabitService(storage)
    water = habits.add(first, " Drink water ")
    stretch = habits.add(first, "Stretch")
    habits.add(second, "Drink water")
    habits.toggle(first, water, date(2026, 7, 14))
    week = habits.view(first, date(2026, 7, 16))
    assert week.start == date(2026, 7, 13)
    assert week.days[-1] == date(2026, 7, 19)
    assert [habit.name for habit in week.habits] == ["Drink water", "Stretch"]
    assert week.checked == {(water, date(2026, 7, 14))}
    assert (week.completed_count, week.completion_percent) == (1, 7)
    assert habits.view(first, date(2026, 7, 20)).completed_count == 0
    assert habits.view(second, date(2026, 7, 14)).completed_count == 0
    with pytest.raises(ValueError, match="Habit not found"):
        habits.toggle(second, water, date(2026, 7, 14))
    with pytest.raises(ValueError, match="Habit not found"):
        habits.delete(second, stretch)
    storage.close()
    storage = Storage(path)
    habits = HabitService(storage)
    assert habits.view(first, date(2026, 7, 14)).completed_count == 1
    habits.toggle(first, water, date(2026, 7, 14))
    assert habits.view(first, date(2026, 7, 14)).completed_count == 0
    habits.toggle(first, stretch, date(2026, 7, 14))
    habits.delete(first, stretch)
    with closing(sqlite3.connect(path)) as db:
        assert db.execute("SELECT count(*) FROM habit_checks").fetchone()[0] == 0
    storage.close()


def test_habit_validation(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "habits.db")
    profile = storage.default_profile_id()
    habits = HabitService(storage)
    for name, message in ((" ", "required"), ("x" * 101, "100 characters")):
        with pytest.raises(ValueError, match=message):
            habits.add(profile, name)
    habit_id = habits.add(profile, "Read")
    with pytest.raises(ValueError, match="already being tracked"):
        habits.add(profile, " read ")
    with pytest.raises(ValueError, match="Profile not found"):
        habits.add(999, "Read")
    with pytest.raises(ValueError, match="Profile not found"):
        habits.view(999, date.today())
    with pytest.raises(ValueError, match="valid day"):
        habits.toggle(profile, habit_id, "2026-07-14")
    assert habits.view(profile, date.today()).completion_percent == 0
    storage.close()


def test_v5_upgrade_snapshot_and_damaged_schema(tmp_path: Path) -> None:
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
        db.execute("PRAGMA user_version=5")
        db.commit()
    upgraded = Storage(path)
    assert HabitService(upgraded).view(profile, date.today()).habits == ()
    upgraded.close()
    with closing(sqlite3.connect(path.with_name("old.db.pre-habits-v5"))) as snapshot:
        assert snapshot.execute("PRAGMA user_version").fetchone()[0] == 5
    with closing(sqlite3.connect(path)) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 17
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        db.execute("DROP TABLE habit_checks")
        db.commit()
    with pytest.raises(RuntimeError, match="missing habit tables"):
        Storage(path)
