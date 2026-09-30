"""Meal weeks, favorites, groceries, ownership, and v10 migration."""

import sqlite3
from contextlib import closing
from datetime import date
from pathlib import Path

import pytest

from solar_forge_desktop.meals import MealService
from solar_forge_desktop.storage import Storage

MONDAY = date(2026, 9, 28)


def test_week_plan_favorites_groceries_isolation_restart(tmp_path: Path) -> None:
    path = tmp_path / "meals.db"
    storage = Storage(path)
    first = storage.default_profile_id()
    second = storage.create_profile("Other")
    service = MealService(storage)
    favorite = service.add_favorite(first, "Taco Bowls", " Rice\n Salsa \nrice \n")
    monday = service.save_plan(first, MONDAY, favorite_id=favorite)
    tuesday = service.save_plan(
        first, date(2026, 9, 29), "Soup", "rice\nCarrots", save_favorite=True
    )
    assert service.save_plan(first, MONDAY, "Pasta") == monday
    assert service.save_plan(first, MONDAY, favorite_id=favorite) == monday
    service.save_plan(second, MONDAY, "Other")
    week = service.view(first, date(2026, 10, 1))
    assert (week.start, week.end) == (MONDAY, date(2026, 10, 4))
    assert [day.weekday() for day, _ in week.days] == list(range(7))
    assert [plan.name for _, plan in week.days[:2]] == ["Taco Bowls", "Soup"]
    assert week.days[2][1] is None
    assert week.groceries == (("Carrots", 1), ("Rice", 3), ("Salsa", 1))
    assert [item.name for item in week.favorites] == ["Soup", "Taco Bowls"]
    assert service.view(second, MONDAY).days[0][1].name == "Other"
    with pytest.raises(ValueError, match="Meal not found"):
        service.delete_plan(second, monday)
    with pytest.raises(ValueError, match="Favorite not found"):
        service.delete_favorite(second, favorite)
    storage.close()
    reopened = Storage(path)
    service = MealService(reopened)
    assert service.view(first, MONDAY).days[1][1].id == tuesday
    service.delete_favorite(first, favorite)
    assert service.view(first, MONDAY).days[0][1].name == "Taco Bowls"
    service.delete_plan(first, monday)
    assert service.view(first, MONDAY).days[0][1] is None
    reopened.close()


def test_validation_and_duplicate_favorites(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "meals.db")
    profile = storage.default_profile_id()
    service = MealService(storage)
    with pytest.raises(ValueError, match="valid day"):
        service.view(profile, "2026-09-28")
    with pytest.raises(ValueError, match="valid day"):
        service.save_plan(profile, "bad", "Soup")
    with pytest.raises(ValueError, match="meal name"):
        service.save_plan(profile, MONDAY, " ")
    with pytest.raises(ValueError, match="Favorite meal name"):
        service.add_favorite(profile, "")
    with pytest.raises(ValueError, match="150 characters"):
        service.add_favorite(profile, "x" * 151)
    with pytest.raises(ValueError, match="Grocery items"):
        service.add_favorite(profile, "Soup", 42)
    with pytest.raises(ValueError, match="Profile not found"):
        service.view(999, MONDAY)
    with pytest.raises(ValueError, match="Profile not found"):
        service.add_favorite(999, "Soup")
    saved = service.add_favorite(profile, " Soup ", "  A\n\n B ")
    with pytest.raises(ValueError, match="already a favorite"):
        service.add_favorite(profile, "soup")
    assert service.view(profile, MONDAY).favorites[0].ingredients == "A\nB"
    service.save_plan(profile, MONDAY, "Soup", save_favorite=True)
    assert len(service.view(profile, MONDAY).favorites) == 1
    service.save_plan(profile, MONDAY, favorite_id=saved)
    with pytest.raises(ValueError, match="Meal not found"):
        service.delete_plan(profile, 999)
    storage.close()


def test_v10_upgrade_snapshot_and_missing_table(tmp_path: Path) -> None:
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
        db.execute("PRAGMA user_version=10")
        db.commit()
    upgraded = Storage(path)
    assert len(MealService(upgraded).view(profile, MONDAY).days) == 7
    upgraded.close()
    with closing(sqlite3.connect(path.with_name("old.db.pre-meals-v10"))) as snapshot:
        assert snapshot.execute("PRAGMA user_version").fetchone()[0] == 10
        assert "meal_plans" not in {
            row[0] for row in snapshot.execute("SELECT name FROM sqlite_master")
        }
    with closing(sqlite3.connect(path)) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 15
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        db.execute("DROP TABLE favorite_meals")
        db.commit()
    with pytest.raises(RuntimeError, match="missing meal tables"):
        Storage(path)
