"""Storage preferences must not change or overwrite the live database."""

from pathlib import Path

import pytest
from PySide6.QtCore import Qt

from solar_forge_desktop.backups import latest_backup
from solar_forge_desktop.configuration import AppSettings, SettingsStore
from solar_forge_desktop.settings_dialog import (
    StorageSettingsDialog,
    save_backup_directory,
    save_storage_locations,
)
from solar_forge_desktop.storage import Storage


def test_save_backup_directory_preserves_active_data_location(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    database = data / "solar-forge-desktop.db"
    database.write_bytes(b"existing data")
    store = SettingsStore(tmp_path / "config")
    store.save(AppSettings(data))
    backup = tmp_path / "backups"

    save_backup_directory(store, data, backup)

    assert store.load() == AppSettings(data, backup)
    assert backup.is_dir()
    assert database.read_bytes() == b"existing data"


def test_reject_backup_in_data_folder(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    store = SettingsStore(tmp_path / "config")
    with pytest.raises(ValueError, match="different folder"):
        save_backup_directory(store, data, data)
    assert store.load() is None


def test_settings_dialog_shows_current_paths(qtbot, tmp_path: Path) -> None:
    data = tmp_path / "data"
    backup = tmp_path / "backup"
    store = SettingsStore(tmp_path / "config")
    store.save(AppSettings(data, backup))
    dialog = StorageSettingsDialog(store, data)
    qtbot.addWidget(dialog)
    assert dialog.data_input.text() == str(data)
    assert not dialog.data_input.isReadOnly()
    assert dialog.backup_input.text() == str(backup)


def test_changing_data_field_queues_move_without_touching_database(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    database = data / "solar-forge-desktop.db"
    database.write_bytes(b"existing data")
    backup = tmp_path / "backups"
    destination = tmp_path / "new data"
    store = SettingsStore(tmp_path / "config")
    store.save(AppSettings(data, backup))

    assert save_storage_locations(store, data, destination, backup, True)

    assert store.load() == AppSettings(data, backup, destination)
    assert database.read_bytes() == b"existing data"
    assert not destination.exists()


def test_launcher_controlled_data_field_is_read_only(qtbot, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SOLAR_FORGE_DESKTOP_DATA_DIR", str(tmp_path / "data"))
    store = SettingsStore(tmp_path / "config")
    dialog = StorageSettingsDialog(store, tmp_path / "data")
    qtbot.addWidget(dialog)
    assert dialog.data_input.isReadOnly()
    with pytest.raises(ValueError, match="controlled by the launcher"):
        save_storage_locations(
            store, tmp_path / "data", tmp_path / "other", tmp_path / "backup", False
        )


def test_settings_can_create_and_verify_backup(qtbot, tmp_path: Path) -> None:
    data = tmp_path / "data"
    storage = Storage(data / "solar-forge-desktop.db")
    storage.create_profile("Family")
    backup = tmp_path / "backup"
    store = SettingsStore(tmp_path / "config")
    store.save(AppSettings(data, backup))
    dialog = StorageSettingsDialog(store, data)
    qtbot.addWidget(dialog)
    dialog.show()

    qtbot.mouseClick(dialog.backup_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: "saved and verified" in dialog.backup_status.text(), timeout=10000)
    assert latest_backup(backup) is not None
    qtbot.mouseClick(dialog.verify_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(
        lambda: dialog.backup_status.text().startswith("Backup verified"), timeout=10000
    )
    dialog.close()
    storage.close()


def test_saving_schedule_keeps_storage_paths(tmp_path: Path) -> None:
    data = tmp_path / "data"
    backup = tmp_path / "backup"
    store = SettingsStore(tmp_path / "config")
    store.save(AppSettings(data, backup))

    assert not save_storage_locations(store, data, data, backup, True, "weekly", 4)
    assert store.load() == AppSettings(
        data, backup, backup_schedule="weekly", backup_retention=4
    )
