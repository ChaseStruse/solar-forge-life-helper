"""A planned move keeps the original database and switches only after verification."""

from pathlib import Path

import pytest

from solar_forge_desktop.configuration import DATABASE_NAME, AppSettings, SettingsStore
from solar_forge_desktop.data_move import perform_pending_move, queue_data_move
from solar_forge_desktop.storage import Storage


def test_pending_move_copies_verifies_and_preserves_source(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source = Storage(source_dir / DATABASE_NAME)
    profile_id = source.create_profile("Family")
    source.close()
    original = (source_dir / DATABASE_NAME).read_bytes()
    store = SettingsStore(tmp_path / "config")
    settings = AppSettings(source_dir, tmp_path / "backups")
    store.save(settings)
    destination = tmp_path / "destination"

    queue_data_move(store, settings, destination)
    assert store.load().pending_move_directory == destination
    assert not destination.exists()
    updated = perform_pending_move(store, store.load())

    assert updated == AppSettings(destination, settings.backup_directory)
    assert store.load() == updated
    assert (source_dir / DATABASE_NAME).read_bytes() == original
    moved = Storage(destination / DATABASE_NAME)
    assert moved.profile_name(profile_id) == "Family"
    moved.close()


def test_move_rejects_existing_target_without_changing_choice(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source = Storage(source_dir / DATABASE_NAME)
    source.close()
    destination = tmp_path / "destination"
    destination.mkdir()
    target = destination / DATABASE_NAME
    target.write_bytes(b"another family's file")
    store = SettingsStore(tmp_path / "config")
    settings = AppSettings(source_dir, tmp_path / "backups")
    store.save(settings)

    with pytest.raises(ValueError, match="already contains"):
        queue_data_move(store, settings, destination)
    assert store.load() == settings
    assert target.read_bytes() == b"another family's file"


def test_failed_copy_keeps_source_selected(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / DATABASE_NAME).write_bytes(b"not sqlite")
    store = SettingsStore(tmp_path / "config")
    settings = AppSettings(source_dir, pending_move_directory=tmp_path / "destination")
    store.save(settings)

    with pytest.raises(Exception):
        perform_pending_move(store, settings)
    assert store.load() == settings
    assert (source_dir / DATABASE_NAME).read_bytes() == b"not sqlite"
    assert not (tmp_path / "destination" / DATABASE_NAME).exists()
