"""Medicine dose rules, storage isolation, and schema upgrade checks."""

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from solar_forge_desktop.medicine import MedicineService
from solar_forge_desktop.storage import Storage


def test_v16_upgrade_preserves_medicine_logs(tmp_path: Path) -> None:
    path = tmp_path / "family.db"
    storage = Storage(path)
    profile = storage.default_profile_id()
    log_id = MedicineService(storage).add_log(
        profile, "Me", "Vitamins", "1 tablet", "2026-10-01T08:00", "2026-10-01T20:00"
    )
    storage.close()
    with closing(sqlite3.connect(path)) as db:
        db.execute("DROP TABLE medicine_reminder_deliveries")
        db.execute("DROP TABLE medicine_reminders")
        db.execute("PRAGMA user_version=16")
        db.commit()

    upgraded = Storage(path)
    assert MedicineService(upgraded).view(profile).logs[0].id == log_id
    upgraded.close()
    with closing(sqlite3.connect(path)) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 18
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    with closing(sqlite3.connect(
        path.with_name("family.db.pre-medicine-reminders-v16")
    )) as snapshot:
        assert snapshot.execute("PRAGMA user_version").fetchone()[0] == 16
        assert snapshot.execute("SELECT COUNT(*) FROM medicine_logs").fetchone()[0] == 1


def test_medicine_doses_order_isolation_delete_and_restart(tmp_path: Path) -> None:
    path = tmp_path / "medicine.db"
    storage = Storage(path)
    first = storage.default_profile_id()
    other = storage.create_profile("Other")
    medicine = MedicineService(storage)
    later = medicine.add_log(
        first, " Max the dog ", " Amoxicillin ", " 10 mg ",
        "2026-07-17T08:00", "2026-07-17T20:00",
    )
    earlier = medicine.add_log(
        first, "Me", "Vitamins", "1 tablet", "2026-07-17T08:00", "2026-07-17T12:00"
    )
    view = medicine.view(first)
    assert view.total_count == 2
    assert [item.id for item in view.logs] == [earlier, later]
    assert view.logs[1].recipient == "Max the dog"
    assert view.logs[1].dosage == "10 mg"
    assert medicine.view(first, 1).total_count == 2
    assert medicine.view(first, 1).recipient_count == 2
    assert [item.id for item in medicine.view(first, 1).logs] == [earlier]
    assert medicine.view(other).logs == ()
    with pytest.raises(ValueError, match="not found"):
        medicine.delete_log(other, earlier)
    storage.close()
    reopened = Storage(path)
    medicine = MedicineService(reopened)
    assert [item.id for item in medicine.view(first).logs] == [earlier, later]
    medicine.delete_log(first, earlier)
    assert [item.id for item in medicine.view(first).logs] == [later]
    reopened.close()


def test_medicine_validation_and_local_wall_times(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "medicine.db")
    profile = storage.default_profile_id()
    medicine = MedicineService(storage)
    valid = ("Max", "Medicine", "10 mg", "2026-07-17T08:00", "2026-07-17T20:00")
    for values, message in (
        ((" ",) + valid[1:], "Who the medicine"),
        (("x" * 101,) + valid[1:], "100 characters"),
        ((valid[0], " ") + valid[2:], "Medicine name"),
        ((valid[0], "x" * 151) + valid[2:], "150 characters"),
        (valid[:2] + (" ",) + valid[3:], "Dosage"),
        (valid[:2] + ("x" * 101,) + valid[3:], "100 characters"),
        (valid[:3] + ("", valid[4]), "times are required"),
        (valid[:4] + ("2026-07-17T08:00",), "scheduled after"),
        (valid[:4] + ("2026-07-17T07:59",), "scheduled after"),
        (valid[:4] + ("2026-02-30T12:00",), "times are required"),
        (valid[:4] + ("2026-7-17T20:00",), "times are required"),
    ):
        with pytest.raises(ValueError, match=message):
            medicine.add_log(profile, *values)
    with pytest.raises(ValueError, match="Profile not found"):
        medicine.add_log(999, *valid)
    with pytest.raises(ValueError, match="Profile not found"):
        medicine.view(999)
    with pytest.raises(ValueError, match="limit"):
        medicine.view(profile, 0)
    with pytest.raises(ValueError, match="limit"):
        medicine.view(profile, 501)
    assert medicine.view(profile).total_count == 0
    storage.close()


def test_v4_upgrade_snapshots_before_medicine_schema(tmp_path: Path) -> None:
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
        db.execute("PRAGMA user_version=4")
        db.commit()
    upgraded = Storage(path)
    assert MedicineService(upgraded).view(profile).logs == ()
    upgraded.close()
    with closing(sqlite3.connect(path.with_name("old.db.pre-medicine-v4"))) as snapshot:
        assert snapshot.execute("PRAGMA user_version").fetchone()[0] == 4
        assert "medicine_logs" not in {
            row[0] for row in snapshot.execute("SELECT name FROM sqlite_master")
        }
    with closing(sqlite3.connect(path)) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 18
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []


@pytest.mark.parametrize(
    ("table", "message"),
    (("medicine_logs", "missing medicine tables"),
     ("journal_entries", "missing journal tables")),
)
def test_v5_rejects_missing_module_table(tmp_path: Path, table: str, message: str) -> None:
    path = tmp_path / f"missing-{table}.db"
    storage = Storage(path)
    storage.close()
    with closing(sqlite3.connect(path)) as db:
        db.execute(f"DROP TABLE {table}")
        db.commit()
    with pytest.raises(RuntimeError, match=message):
        Storage(path)
