"""Workout entries, validation, profile boundaries, and v8 migration."""

import sqlite3
from contextlib import closing
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from solar_forge_desktop.storage import Storage
from solar_forge_desktop.workout import WorkoutService

DAY = date(2026, 9, 28)


def test_daily_entries_edit_delete_restart_and_profile_isolation(tmp_path: Path) -> None:
    path = tmp_path / "workout.db"
    storage = Storage(path)
    first = storage.default_profile_id()
    second = storage.create_profile("Other")
    service = WorkoutService(storage)
    weighted = service.add(first, DAY, " Bench press ", 3, 8, False, "135.125", " Good form ")
    bodyweight = service.add(first, DAY, "Pull ups", 4, 6, True, "999")
    service.add(second, DAY, "Squats", 5, 10, False)
    view = service.view(first, DAY)
    assert (view.exercise_count, view.total_sets, view.total_reps) == (2, 7, 14)
    assert [item.id for item in view.exercises] == [weighted, bodyweight]
    assert view.exercises[0].weight_lbs == Decimal("135.125")
    assert view.exercises[0].notes == "Good form"
    assert view.exercises[1].weight_lbs is None
    assert service.view(second, DAY).exercise_count == 1
    assert service.view(first, date(2026, 9, 27)).exercise_count == 0
    with pytest.raises(ValueError, match="not found"):
        service.edit(second, weighted, "No", 1, 1, False)
    with pytest.raises(ValueError, match="not found"):
        service.delete(second, weighted)
    service.edit(first, weighted, "Bench", 2, 10, True, "135")
    assert service.view(first, DAY).exercises[0].weight_lbs is None
    assert service.view(first, DAY).total_reps == 16
    storage.close()
    reopened = Storage(path)
    service = WorkoutService(reopened)
    assert service.view(first, DAY).exercises[0].exercise_name == "Bench"
    service.delete(first, weighted)
    assert service.view(first, DAY).exercise_count == 1
    reopened.close()


def test_validation_and_bounded_rows_keep_full_summary(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "workout.db")
    profile = storage.default_profile_id()
    service = WorkoutService(storage)
    for name, sets, reps, bodyweight, weight, message in (
        (" ", 1, 1, False, None, "name is required"),
        ("x" * 151, 1, 1, False, None, "150 characters"),
        ("Run", 0, 1, False, None, "Sets must be at least 1"),
        ("Run", 1.5, 1, False, None, "Sets must be a whole number"),
        ("Run", 1, 0, False, None, "Reps must be at least 1"),
        ("Run", 1, True, False, None, "Reps must be a whole number"),
        ("Run", 1, 1, False, "NaN", "valid number"),
        ("Run", 1, 1, False, "bad", "valid number"),
        ("Run", 1, 1, False, 135, "valid number"),
        ("Run", 1, 1, False, "-1", "cannot be negative"),
        ("Run", 1, 1, "yes", None, "bodyweight setting"),
    ):
        with pytest.raises(ValueError, match=message):
            service.add(profile, DAY, name, sets, reps, bodyweight, weight)
    with pytest.raises(ValueError, match="valid date"):
        service.add(profile, "2026-09-28", "Run", 1, 1, False)
    with pytest.raises(ValueError, match="Profile not found"):
        service.view(999, DAY)
    with pytest.raises(ValueError, match="Profile not found"):
        service.add(999, DAY, "Run", 1, 1, False)
    with pytest.raises(ValueError, match="limit"):
        service.view(profile, DAY, 0)
    service.add(profile, DAY, "First", 3, 10, False, "0")
    service.add(profile, DAY, "Second", 2, 5, False)
    day = service.view(profile, DAY, 1)
    assert (day.exercise_count, day.total_sets, day.total_reps) == (2, 5, 15)
    assert [entry.exercise_name for entry in day.exercises] == ["Second"]
    assert service.view(profile, DAY).exercises[0].weight_lbs == Decimal(0)
    storage.close()


def test_v8_upgrade_snapshot_and_missing_table(tmp_path: Path) -> None:
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
        db.execute("PRAGMA user_version=8")
        db.commit()
    upgraded = Storage(path)
    assert WorkoutService(upgraded).view(profile, DAY).exercise_count == 0
    upgraded.close()
    with closing(sqlite3.connect(path.with_name("old.db.pre-workout-v8"))) as snapshot:
        assert snapshot.execute("PRAGMA user_version").fetchone()[0] == 8
        assert "workout_logs" not in {
            row[0] for row in snapshot.execute("SELECT name FROM sqlite_master")
        }
    with closing(sqlite3.connect(path)) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 14
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        db.execute("DROP TABLE workout_logs")
        db.commit()
    with pytest.raises(RuntimeError, match="missing workout tables"):
        Storage(path)
