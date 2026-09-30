"""Maintenance recurrence, exact costs, ownership, and v11 upgrade."""

import sqlite3
from contextlib import closing
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from solar_forge_desktop.maintenance import MaintenanceService, advance_date
from solar_forge_desktop.storage import Storage

TODAY = date(2026, 7, 19)


def test_calendar_advancement_and_scheduled_completion(tmp_path: Path) -> None:
    assert advance_date(date(2026, 1, 31), 1, "months") == date(2026, 2, 28)
    assert advance_date(date(2024, 2, 29), 1, "years") == date(2025, 2, 28)
    assert advance_date(date(2026, 7, 1), 2, "weeks") == date(2026, 7, 15)
    assert advance_date(date(2026, 7, 1), 3, "days") == date(2026, 7, 4)
    storage = Storage(tmp_path / "maintenance.db")
    profile = storage.default_profile_id()
    service = MaintenanceService(storage)
    overdue = service.add(profile, "Filter", "Appliances", date(2026, 7, 1), 1,
                          "months", "18.50", "Size 16x20")
    future = service.add(profile, "Test alarm", "Safety", date(2026, 7, 20), 1,
                         "months")
    soon = service.add(profile, "Wash windows", "Cleaning", date(2026, 8, 1), 2,
                       "weeks", "0")
    view = service.view(profile, TODAY)
    assert (view.total, view.overdue, view.due_soon) == (3, 1, 2)
    assert [entry.id for entry in view.items] == [overdue, future, soon]
    assert [entry.status for entry in view.items] == ["overdue", "soon", "soon"]
    assert view.items[0].estimated_cost == Decimal("18.50")
    assert service.complete(profile, overdue, TODAY) == date(2026, 8, 1)
    assert service.complete(profile, future, TODAY) == date(2026, 8, 20)
    assert service.view(profile, TODAY).items[0].last_completed_date == TODAY
    assert service.complete(profile, soon, TODAY) == date(2026, 8, 15)
    storage.close()


def test_overdue_catchup_isolation_restart_and_delete(tmp_path: Path) -> None:
    path = tmp_path / "maintenance.db"
    storage = Storage(path)
    first = storage.default_profile_id()
    second = storage.create_profile("Other")
    service = MaintenanceService(storage)
    entry = service.add(first, "Old task", "General", date(2026, 1, 31), 1, "months")
    service.add(second, "Other task", "Vehicle", TODAY, 1, "years")
    assert service.complete(first, entry, TODAY) == date(2026, 7, 28)
    assert service.view(first, TODAY).total == 1
    assert service.view(second, TODAY).total == 1
    with pytest.raises(ValueError, match="not found"):
        service.complete(second, entry, TODAY)
    with pytest.raises(ValueError, match="not found"):
        service.delete(second, entry)
    storage.close()
    reopened = Storage(path)
    service = MaintenanceService(reopened)
    assert service.view(first, TODAY).items[0].next_due_date == date(2026, 7, 28)
    service.delete(first, entry)
    assert service.view(first, TODAY).total == 0
    reopened.close()


def test_validation_and_bounded_summary(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "maintenance.db")
    profile = storage.default_profile_id()
    service = MaintenanceService(storage)
    base = (profile, "Filter", "General", TODAY, 1, "months")
    for args, message in (
        ((profile, "", "General", TODAY, 1, "months"), "name is required"),
        ((profile, "Filter", "Wrong", TODAY, 1, "months"), "valid category"),
        ((profile, "Filter", "General", "2026-07-19", 1, "months"), "valid next due"),
        ((profile, "Filter", "General", TODAY, 0, "months"), "repeat interval"),
        ((profile, "Filter", "General", TODAY, 1000, "months"), "repeat interval"),
        ((profile, "Filter", "General", TODAY, 1, "centuries"), "repeat unit"),
    ):
        with pytest.raises(ValueError, match=message):
            service.add(*args)
    for cost in ("-1", "NaN", "Infinity", "nope"):
        with pytest.raises(ValueError, match="zero or greater"):
            service.add(*base, cost_raw=cost)
    with pytest.raises(ValueError, match="too large"):
        service.add(*base, cost_raw="1e99999")
    with pytest.raises(ValueError, match="Profile not found"):
        service.view(999, TODAY)
    with pytest.raises(ValueError, match="limit"):
        service.view(profile, TODAY, 0)
    service.add(*base)
    service.add(profile, "Roof", "Exterior", TODAY, 1, "years")
    assert service.view(profile, TODAY, 1).total == 2
    assert len(service.view(profile, TODAY, 1).items) == 1
    storage.close()


def test_v11_upgrade_snapshot_and_missing_table(tmp_path: Path) -> None:
    path = tmp_path / "old.db"
    storage = Storage(path)
    profile = storage.default_profile_id()
    storage.close()
    with closing(sqlite3.connect(path)) as db:
        db.execute("DROP TABLE profile_settings")
        db.execute("DROP TABLE calendar_events")
        db.execute("DROP TABLE maintenance_items")
        db.execute("PRAGMA user_version=11")
        db.commit()
    upgraded = Storage(path)
    assert MaintenanceService(upgraded).view(profile, TODAY).total == 0
    upgraded.close()
    with closing(sqlite3.connect(path.with_name("old.db.pre-maintenance-v11"))) as snapshot:
        assert snapshot.execute("PRAGMA user_version").fetchone()[0] == 11
        assert "maintenance_items" not in {
            row[0] for row in snapshot.execute("SELECT name FROM sqlite_master")
        }
    with closing(sqlite3.connect(path)) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 15
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        db.execute("DROP TABLE maintenance_items")
        db.commit()
    with pytest.raises(RuntimeError, match="missing maintenance tables"):
        Storage(path)
