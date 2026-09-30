"""Restore switches data only after verification and keeps a recovery snapshot."""

from pathlib import Path

import pytest

import solar_forge_desktop.restore as restore_module
from solar_forge_desktop.backups import create_backup, verify_backup
from solar_forge_desktop.configuration import DATABASE_NAME, AppSettings, SettingsStore
from solar_forge_desktop.restore import perform_pending_restore, queue_restore
from solar_forge_desktop.storage import Storage


def test_restore_previous_snapshot_and_keep_current_data(tmp_path: Path) -> None:
    data = tmp_path / "data"
    database = data / DATABASE_NAME
    storage = Storage(database)
    old_id = storage.create_profile("Earlier")
    backups = tmp_path / "backups"
    selected = create_backup(database, backups)
    storage.create_profile("Recent")
    storage.close()
    store = SettingsStore(tmp_path / "config")
    settings = AppSettings(data, backups)
    store.save(settings)

    queue_restore(store, settings, selected.manifest)
    safety = perform_pending_restore(store, store.load(), data)

    assert safety is not None
    assert "pre-restore" in safety.database.name
    assert verify_backup(safety.manifest) == safety
    assert store.load() == settings
    restored = Storage(database)
    assert restored.profile_name(old_id) == "Earlier"
    with pytest.raises(ValueError, match="not found"):
        restored.profile_name(old_id + 1)
    restored.close()
    recovery = Storage(safety.database)
    assert recovery.profile_name(old_id + 1) == "Recent"
    recovery.close()


def test_tampered_backup_does_not_change_current_database(tmp_path: Path) -> None:
    data = tmp_path / "data"
    database = data / DATABASE_NAME
    storage = Storage(database)
    profile_id = storage.create_profile("Current")
    storage.close()
    backups = tmp_path / "backups"
    selected = create_backup(database, backups)
    store = SettingsStore(tmp_path / "config")
    settings = AppSettings(data, backups)
    store.save(settings)
    selected.database.write_bytes(b"tampered")

    with pytest.raises(ValueError, match="does not match"):
        queue_restore(store, settings, selected.manifest)
    assert store.load() == settings
    current = Storage(database)
    assert current.profile_name(profile_id) == "Current"
    current.close()


def test_failed_reopen_rolls_back_from_safety_copy(tmp_path: Path, monkeypatch) -> None:
    data = tmp_path / "data"
    database = data / DATABASE_NAME
    storage = Storage(database)
    storage.create_profile("Before backup")
    backups = tmp_path / "backups"
    selected = create_backup(database, backups)
    newest_id = storage.create_profile("Newest")
    storage.close()
    store = SettingsStore(tmp_path / "config")
    settings = AppSettings(data, backups)
    store.save(settings)
    queue_restore(store, settings, selected.manifest)
    real_storage = Storage
    calls = 0

    def fail_once(path: Path):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("simulated open failure")
        return real_storage(path)

    monkeypatch.setattr(restore_module, "Storage", fail_once)
    with pytest.raises(RuntimeError, match="simulated open failure"):
        perform_pending_restore(store, store.load(), data)
    current = real_storage(database)
    assert current.profile_name(newest_id) == "Newest"
    current.close()
