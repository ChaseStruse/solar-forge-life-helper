"""Storage preferences must not change or overwrite the live database."""

from pathlib import Path

import pytest

from solar_forge_desktop.configuration import AppSettings, SettingsStore
from solar_forge_desktop.settings_dialog import StorageSettingsDialog, save_backup_directory


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
    assert dialog.data_input.isReadOnly()
    assert dialog.backup_input.text() == str(backup)
