"""Pet profiles, nested ownership, medicine matching, and schema upgrade."""

import sqlite3
from contextlib import closing
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from solar_forge_desktop.medicine import MedicineService
from solar_forge_desktop.pets import PetService
from solar_forge_desktop.storage import Storage

DAY = date(2026, 9, 28)


def test_pet_care_selection_medicine_cascade_restart_and_isolation(tmp_path: Path) -> None:
    path = tmp_path / "pets.db"
    storage = Storage(path)
    first = storage.default_profile_id()
    second = storage.create_profile("Other")
    service = PetService(storage)
    assert service.view(first).selected is None
    luna = service.add_pet(first, " Luna ", "Dog", "Lab", date(2020, 5, 1), "Likes carrots")
    milo = service.add_pet(first, "Milo", "Cat")
    other = service.add_pet(second, "Luna", "Cat")
    feeding = service.add_record(first, luna, "feeding", DAY, "Morning meal")
    weight = service.add_record(first, luna, "weight", DAY, "Home scale", "42.125")
    service.add_record(first, milo, "grooming", DAY, "Brushed")
    MedicineService(storage).add_log(
        first, "Luna", "Heartgard", "1 chew", "2026-09-27T08:00", "2026-10-27T08:00"
    )
    MedicineService(storage).add_log(
        second, "Luna", "Other dose", "1 chew", "2026-09-27T08:00", "2026-10-27T08:00"
    )
    view = service.view(first, luna)
    assert [pet.name for pet in view.pets] == ["Luna", "Milo"]
    assert (view.care_count, view.medicine_count) == (2, 1)
    assert view.records[0].weight == Decimal("42.125")
    assert view.records[1].details == "Morning meal"
    assert view.medicines[0].medicine_name == "Heartgard"
    assert service.view(first, milo).care_count == 1
    assert service.view(first, 999).selected.id == luna
    assert service.view(second).selected.id == other
    with pytest.raises(ValueError, match="Pet not found"):
        service.add_record(second, luna, "note", DAY, "Intrusion")
    with pytest.raises(ValueError, match="Care record not found"):
        service.delete_record(second, luna, feeding)
    with pytest.raises(ValueError, match="Pet not found"):
        service.delete_pet(second, luna)
    assert service.view(first, luna, 1).care_count == 2
    assert len(service.view(first, luna, 1).records) == 1
    storage.close()
    reopened = Storage(path)
    service = PetService(reopened)
    assert service.view(first, luna).selected.notes == "Likes carrots"
    service.delete_record(first, luna, weight)
    service.delete_pet(first, luna)
    assert service.view(first).selected.id == milo
    assert service.view(second).selected.id == other
    with closing(sqlite3.connect(path)) as db:
        count = db.execute("SELECT COUNT(*) FROM pet_care_records WHERE pet_id=?", (luna,))
        assert count.fetchone()[0] == 0
    reopened.close()


def test_validation_and_weight_rules(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "pets.db")
    profile = storage.default_profile_id()
    service = PetService(storage)
    with pytest.raises(ValueError, match="Pet name and animal type"):
        service.add_pet(profile, "", "Dog")
    with pytest.raises(ValueError, match="Pet name and animal type"):
        service.add_pet(profile, "Luna", "")
    with pytest.raises(ValueError, match="100 characters"):
        service.add_pet(profile, "x" * 101, "Dog")
    with pytest.raises(ValueError, match="Animal type must be 60 characters"):
        service.add_pet(profile, "Luna", "x" * 61)
    for invalid_birth in ("", False, 0):
        with pytest.raises(ValueError, match="valid birth date"):
            service.add_pet(profile, "Luna", "Dog", birth_date=invalid_birth)
    with pytest.raises(ValueError, match="valid birth date"):
        service.add_pet(profile, "Luna", "Dog", birth_date="2020-01-01")
    with pytest.raises(ValueError, match="future"):
        service.add_pet(profile, "Luna", "Dog", birth_date=date(2999, 1, 1))
    with pytest.raises(ValueError, match="Profile not found"):
        service.add_pet(999, "Luna", "Dog")
    pet = service.add_pet(profile, "Luna", "Dog")
    for category, day, details, weight, message in (
        ("other", DAY, "Text", None, "valid care type"),
        ("note", DAY, " ", None, "Care details"),
        ("note", "2026-09-28", "Text", None, "valid date"),
        ("weight", DAY, "Scale", "0", "greater than zero"),
        ("weight", DAY, "Scale", "NaN", "greater than zero"),
        ("weight", DAY, "Scale", None, "greater than zero"),
    ):
        with pytest.raises(ValueError, match=message):
            service.add_record(profile, pet, category, day, details, weight)
    service.add_record(profile, pet, "note", DAY, "Text", "999")
    assert service.view(profile).records[0].weight is None
    with pytest.raises(ValueError, match="Profile not found"):
        service.view(999)
    with pytest.raises(ValueError, match="limit"):
        service.view(profile, limit=0)
    storage.close()


def test_v9_upgrade_snapshot_and_missing_table(tmp_path: Path) -> None:
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
        db.execute("PRAGMA user_version=9")
        db.commit()
    upgraded = Storage(path)
    assert PetService(upgraded).view(profile).selected is None
    upgraded.close()
    with closing(sqlite3.connect(path.with_name("old.db.pre-pets-v9"))) as snapshot:
        assert snapshot.execute("PRAGMA user_version").fetchone()[0] == 9
        assert "pets" not in {row[0] for row in snapshot.execute("SELECT name FROM sqlite_master")}
    with closing(sqlite3.connect(path)) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 15
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        db.execute("DROP TABLE pet_care_records")
        db.commit()
    with pytest.raises(RuntimeError, match="missing pet tables"):
        Storage(path)
