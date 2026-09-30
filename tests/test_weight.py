"""Weight progression, exact readings, isolation, and schema upgrade."""

import sqlite3
from contextlib import closing
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from solar_forge_desktop.storage import Storage
from solar_forge_desktop.weight import WeightService

START = date(2026, 7, 1)
TARGET = date(2026, 8, 1)


def test_loss_goal_daily_upsert_differences_restart_and_isolation(tmp_path: Path) -> None:
    path = tmp_path / "weight.db"
    storage = Storage(path)
    first = storage.default_profile_id()
    second = storage.create_profile("Other")
    service = WeightService(storage)
    assert service.view(first).latest_weight is None
    service.set_goal(first, "200.0", START, "180.0", TARGET)
    assert service.view(first).latest_weight == Decimal("200.0")
    initial, updated = service.log(first, date(2026, 7, 10), "198.125")
    assert not updated
    latest, _ = service.log(first, date(2026, 7, 17), "195.5")
    assert service.log(first, date(2026, 7, 17), "194.2") == (latest, True)
    view = service.view(first)
    assert view.total_logs == 2
    assert [item.id for item in view.logs] == [latest, initial]
    assert [item.difference for item in view.logs] == [
        Decimal("-3.925"), Decimal("-1.875")
    ]
    assert view.chart_points[0] == (START, Decimal("200.0"))
    assert view.latest_weight == Decimal("194.2")
    assert (view.total_change, view.remaining, view.progress_percent) == (
        Decimal("-5.8"), Decimal("14.2"), 29
    )
    assert service.view(first, 1).logs[0].difference == Decimal("-3.925")
    assert service.view(second).goal is None
    with pytest.raises(ValueError, match="not found"):
        service.delete(second, initial)
    storage.close()
    reopened = Storage(path)
    service = WeightService(reopened)
    assert service.view(first).logs[0].weight == Decimal("194.2")
    service.delete(first, latest)
    assert service.view(first).latest_weight == Decimal("198.125")
    reopened.close()


def test_gain_goal_progress_and_goal_update(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "weight.db")
    profile = storage.default_profile_id()
    service = WeightService(storage)
    service.set_goal(profile, "150", START, "160", TARGET)
    service.log(profile, date(2026, 7, 14), "155")
    view = service.view(profile)
    assert not view.is_losing
    assert (view.total_change, view.remaining, view.progress_percent) == (
        Decimal("5"), Decimal("5"), 50
    )
    service.log(profile, date(2026, 7, 21), "165")
    assert service.view(profile).progress_percent == 100
    service.set_goal(profile, "150", START, "155", TARGET)
    assert service.view(profile).goal.target_weight == Decimal("155")
    service.set_goal(profile, "150", START, "150", TARGET)
    assert service.view(profile).progress_percent == 0
    storage.close()


def test_weight_validation_and_log_without_goal(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "weight.db")
    profile = storage.default_profile_id()
    service = WeightService(storage)
    for value, message in (("abc", "valid numbers"), ("NaN", "valid numbers"),
                           ("0", "greater than zero")):
        with pytest.raises(ValueError, match=message):
            service.set_goal(profile, value, START, "180", TARGET)
    with pytest.raises(ValueError, match="after the starting date"):
        service.set_goal(profile, "200", TARGET, "180", START)
    with pytest.raises(ValueError, match="valid date"):
        service.set_goal(profile, "200", "2026-07-01", "180", TARGET)
    for value, message in (("abc", "valid weight"), ("Infinity", "valid weight"),
                           ("0", "greater than zero")):
        with pytest.raises(ValueError, match=message):
            service.log(profile, START, value)
    with pytest.raises(ValueError, match="valid date"):
        service.log(profile, "2026-07-14", "150")
    with pytest.raises(ValueError, match="Profile not found"):
        service.view(999)
    with pytest.raises(ValueError, match="Profile not found"):
        service.log(999, START, "150")
    with pytest.raises(ValueError, match="Profile not found"):
        service.set_goal(999, "200", START, "180", TARGET)
    with pytest.raises(ValueError, match="limit"):
        service.view(profile, 0)
    service.log(profile, START, "180.01")
    view = service.view(profile)
    assert view.latest_weight == Decimal("180.01")
    assert view.logs[0].difference == 0
    storage.close()


def test_v7_upgrade_snapshot_and_missing_table(tmp_path: Path) -> None:
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
        db.execute("PRAGMA user_version=7")
        db.commit()
    upgraded = Storage(path)
    assert WeightService(upgraded).view(profile).goal is None
    upgraded.close()
    with closing(sqlite3.connect(path.with_name("old.db.pre-weight-v7"))) as snapshot:
        assert snapshot.execute("PRAGMA user_version").fetchone()[0] == 7
        assert "weight_logs" not in {
            row[0] for row in snapshot.execute("SELECT name FROM sqlite_master")
        }
    with closing(sqlite3.connect(path)) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 16
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        db.execute("DROP TABLE weight_logs")
        db.commit()
    with pytest.raises(RuntimeError, match="missing weight tables"):
        Storage(path)
