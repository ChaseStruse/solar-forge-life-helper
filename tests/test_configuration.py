"""Settings stay outside SQLite and do not hide a missing selected database."""

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from solar_forge_desktop.bootstrap import import_legacy_database
from solar_forge_desktop.configuration import (
    DATABASE_NAME,
    AppSettings,
    DataLocationUnavailable,
    SettingsStore,
    resolve_data_directory,
)
from solar_forge_desktop.storage import Storage


def test_settings_round_trip_and_location_precedence(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path / "config")
    default = tmp_path / "default"
    selected = tmp_path / "family data"
    selected.mkdir()
    (selected / DATABASE_NAME).touch()
    assert store.load() is None
    assert resolve_data_directory(None, default, {}) == default

    settings = AppSettings(selected, tmp_path / "backups")
    store.save(settings)
    assert store.load() == settings
    assert resolve_data_directory(store.load(), default, {}) == selected
    assert resolve_data_directory(
        store.load(), default, {"SOLAR_FORGE_DESKTOP_DATA_DIR": str(tmp_path / "override")}
    ) == tmp_path / "override"
    assert store.path.stat().st_mode & 0o077 == 0

    scheduled = AppSettings(selected, tmp_path / "backups", backup_schedule="daily",
                            backup_retention=3)
    store.save(scheduled)
    assert store.load() == scheduled


def test_saved_location_must_remain_available(tmp_path: Path) -> None:
    selected = tmp_path / "detached drive"
    settings = AppSettings(selected)
    with pytest.raises(DataLocationUnavailable, match="Reconnect its drive"):
        resolve_data_directory(settings, tmp_path / "default", {})
    selected.mkdir()
    with pytest.raises(DataLocationUnavailable, match="selected database is unavailable"):
        resolve_data_directory(settings, tmp_path / "default", {})
    assert not (selected / DATABASE_NAME).exists()


def test_invalid_settings_do_not_fall_back_to_new_database(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path)
    store.path.write_text("{broken", encoding="utf-8")
    with pytest.raises(ValueError, match="Could not read application settings"):
        store.load()
    with pytest.raises(ValueError, match="absolute path"):
        store.save(AppSettings(Path("relative/data")))
    assert store.path.read_text(encoding="utf-8") == "{broken"


def test_legacy_import_uses_explicit_folder_and_restores_app_identity(
    qtbot, tmp_path: Path,
) -> None:
    app = QApplication.instance()
    app.setOrganizationName("Solar Forge Life Helper")
    app.setApplicationName("Solar Forge Life Helper")
    old_directory = tmp_path / "old"
    old_database = old_directory / "luna-desktop.db"
    source = Storage(old_database)
    source.close()
    destination = tmp_path / "new" / DATABASE_NAME
    import_legacy_database(
        app, destination, {"SOLAR_FORGE_DESKTOP_LEGACY_DATA_DIR": str(old_directory)}
    )
    assert destination.is_file()
    assert old_database.is_file()
    assert app.organizationName() == "Solar Forge Life Helper"
