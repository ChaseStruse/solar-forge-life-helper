"""Calorie rules, isolation, persistence, and schema migration."""

import sqlite3
from contextlib import closing
from datetime import date
from pathlib import Path

import pytest

from solar_forge_desktop.calorie import CalorieService
from solar_forge_desktop.storage import Storage

DAY = date(2026, 7, 14)


def test_goal_fallback_daily_totals_and_profile_isolation(tmp_path: Path) -> None:
    path = tmp_path / "calorie.db"
    storage = Storage(path)
    first = storage.default_profile_id()
    second = storage.create_profile("Other")
    service = CalorieService(storage)
    assert service.view(first, DAY).target == 2000
    service.set_goal(first, date(2026, 7, 20), "2100")
    assert service.view(first, DAY).target == 2100
    service.set_goal(first, date(2026, 7, 10), "1800")
    assert service.view(first, DAY).target == 1800
    service.set_goal(first, DAY, "2250")
    service.set_goal(first, DAY, "2300")
    assert (service.view(first, DAY).target, service.view(first, DAY).has_custom_goal) == (
        2300, True
    )
    first_food = service.add_food(first, DAY, " Oatmeal ", "320")
    second_food = service.add_food(first, DAY, "Coffee", "0")
    view = service.view(first, DAY, 1)
    assert (view.consumed, view.remaining, view.progress_percent, view.total_logs) == (
        320, 1980, 13, 2
    )
    assert len(view.foods) == 1
    assert service.view(second, DAY).target == 2000
    assert service.view(second, DAY).foods == ()
    with pytest.raises(ValueError, match="not found"):
        service.delete_food(second, first_food)
    storage.close()
    reopened = Storage(path)
    service = CalorieService(reopened)
    assert {item.id for item in service.view(first, DAY).foods} == {first_food, second_food}
    service.delete_food(first, second_food)
    assert service.view(first, DAY).consumed == 320
    service.delete_food(first, first_food)
    assert service.view(first, DAY).total_logs == 0
    reopened.close()


def test_calorie_validation_and_over_target(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "calorie.db")
    profile = storage.default_profile_id()
    service = CalorieService(storage)
    for value, message in (("", "valid integer"), ("1.5", "valid integer"),
                           ("0", "greater than zero"), ("10001", "10,000")):
        with pytest.raises(ValueError, match=message):
            service.set_goal(profile, DAY, value)
    for name, calories, message in (
        (" ", "100", "Food name is required"),
        ("x" * 101, "100", "100 characters"),
        ("Apple", "abc", "valid integer"),
        ("Apple", "-1", "cannot be negative"),
        ("Apple", "5001", "5,000"),
    ):
        with pytest.raises(ValueError, match=message):
            service.add_food(profile, DAY, name, calories)
    with pytest.raises(ValueError, match="valid date"):
        service.view(profile, "2026-07-14")
    with pytest.raises(ValueError, match="Profile not found"):
        service.view(999, DAY)
    with pytest.raises(ValueError, match="Profile not found"):
        service.add_food(999, DAY, "Apple", "100")
    with pytest.raises(ValueError, match="Profile not found"):
        service.set_goal(999, DAY, "2000")
    with pytest.raises(ValueError, match="limit"):
        service.view(profile, DAY, 0)
    service.set_goal(profile, DAY, "100")
    service.add_food(profile, DAY, "Meal", "250")
    view = service.view(profile, DAY)
    assert (view.consumed, view.remaining, view.progress_percent) == (250, -150, 100)
    storage.close()


def test_v6_upgrade_snapshot_and_missing_tables(tmp_path: Path) -> None:
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
        db.execute("DROP TABLE food_logs")
        db.execute("DROP TABLE calorie_goals")
        db.execute("PRAGMA user_version=6")
        db.commit()
    upgraded = Storage(path)
    assert CalorieService(upgraded).view(profile, DAY).target == 2000
    upgraded.close()
    with closing(sqlite3.connect(path.with_name("old.db.pre-calorie-v6"))) as snapshot:
        assert snapshot.execute("PRAGMA user_version").fetchone()[0] == 6
        assert "food_logs" not in {
            row[0] for row in snapshot.execute("SELECT name FROM sqlite_master")
        }
    with closing(sqlite3.connect(path)) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 17
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        db.execute("DROP TABLE food_logs")
        db.commit()
    with pytest.raises(RuntimeError, match="missing calorie tables"):
        Storage(path)
