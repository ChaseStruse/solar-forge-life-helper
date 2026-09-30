"""Settings stay outside SQLite and do not hide a missing selected database."""

from pathlib import Path

import pytest

from solar_forge_desktop.configuration import (
    DATABASE_NAME,
    AppSettings,
    DataLocationUnavailable,
    SettingsStore,
    resolve_data_directory,
)


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
