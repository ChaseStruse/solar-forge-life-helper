import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from sqlalchemy import text

from solar_forge_desktop.storage import Storage, seed_database_from_legacy
from solar_forge_desktop.tasks import TaskService


def test_tasks_persist_with_order_and_completion_time(tmp_path: Path) -> None:
    path = tmp_path / "data #1" / "solar-forge.db"
    storage = Storage(path)
    profile = storage.default_profile_id()
    service = TaskService(storage)
    first = service.add_task(profile, " First ")
    second = service.add_task(profile, "Second")
    assert [task.title for task in service.list_tasks(profile)[0]] == ["Second", "First"]
    service.toggle_task(profile, first)
    active, completed = service.list_tasks(profile)
    assert [task.id for task in active] == [second]
    assert completed[0].completed_at is not None
    storage.close()

    reopened = Storage(path)
    service = TaskService(reopened)
    assert [task.id for task in service.list_tasks(profile)[1]] == [first]
    service.toggle_task(profile, first)
    assert service.list_tasks(profile)[1] == []
    assert service.list_tasks(profile)[0][1].completed_at is None
    service.delete_task(profile, second)
    assert len(service.list_tasks(profile)[0]) == 1
    reopened.close()


def test_task_validation_and_profile_ownership(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "solar-forge.db")
    service = TaskService(storage)
    first = storage.default_profile_id()
    other = storage.create_profile("Other")
    assert storage.profile_name(other) == "Other"
    with pytest.raises(ValueError, match="Profile not found"):
        storage.profile_name(9999)
    task = service.add_task(first, "Private")
    assert service.list_tasks(other) == ([], [])
    with pytest.raises(ValueError, match="title is required"):
        service.add_task(first, "  ")
    with pytest.raises(ValueError, match="200 characters"):
        service.add_task(first, "x" * 201)
    with pytest.raises(ValueError, match="Profile not found"):
        service.add_task(9999, "Orphan")
    with pytest.raises(ValueError, match="Task not found"):
        service.toggle_task(other, task)
    with pytest.raises(ValueError, match="Task not found"):
        service.delete_task(other, task)
    assert service.list_tasks(first)[0][0].title == "Private"
    storage.close()


def test_rejects_legacy_and_newer_schema_without_modifying_source(tmp_path: Path) -> None:
    path = tmp_path / "legacy.db"
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("CREATE TABLE users (id INTEGER PRIMARY KEY)")
        connection.commit()
    original = path.read_bytes()
    with pytest.raises(RuntimeError, match="not a new Solar Forge Python desktop database"):
        Storage(path)
    assert path.read_bytes() == original

    path = tmp_path / "newer.db"
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("PRAGMA user_version=99")
        connection.commit()
    original = path.read_bytes()
    with pytest.raises(RuntimeError, match="Unsupported desktop database version"):
        Storage(path)
    assert path.read_bytes() == original


def test_foreign_keys_enabled(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "solar-forge.db")
    with storage.engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
    storage.close()


def test_seed_database_from_legacy_preserves_source_and_data(tmp_path: Path) -> None:
    legacy_path = tmp_path / "legacy data" / "luna-desktop.db"
    legacy = Storage(legacy_path)
    profile = legacy.default_profile_id()
    service = TaskService(legacy)
    task_id = service.add_task(profile, "Keep this task")
    legacy.close()
    source_bytes = legacy_path.read_bytes()

    destination_path = tmp_path / "volume" / "solar-forge-desktop.db"
    assert seed_database_from_legacy(legacy_path, destination_path) is True
    assert destination_path.is_file()
    assert legacy_path.read_bytes() == source_bytes
    migrated = Storage(destination_path)
    assert [task.id for task in TaskService(migrated).list_tasks(profile)[0]] == [task_id]
    migrated.close()
    assert seed_database_from_legacy(legacy_path, destination_path) is False
    assert seed_database_from_legacy(tmp_path / "missing.db", tmp_path / "other.db") is False


def test_seed_database_from_legacy_rejects_unknown_schema(tmp_path: Path) -> None:
    legacy_path = tmp_path / "unknown.db"
    with closing(sqlite3.connect(legacy_path)) as connection:
        connection.execute("CREATE TABLE unknown (id INTEGER PRIMARY KEY)")
        connection.commit()
    source_bytes = legacy_path.read_bytes()
    destination_path = tmp_path / "volume" / "solar-forge-desktop.db"
    with pytest.raises(RuntimeError, match="unsupported schema"):
        seed_database_from_legacy(legacy_path, destination_path)
    assert legacy_path.read_bytes() == source_bytes
    assert not destination_path.exists()
