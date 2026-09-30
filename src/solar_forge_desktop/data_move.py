"""Copy a database at startup, before any page or worker opens it."""

import os
import sqlite3
import tempfile
from contextlib import closing
from dataclasses import replace
from pathlib import Path
from urllib.parse import quote

from solar_forge_desktop.configuration import DATABASE_NAME, AppSettings, SettingsStore
from solar_forge_desktop.storage import Storage


def validate_move_target(settings: AppSettings, destination: Path) -> Path:
    """Check a requested destination without changing settings or touching files."""
    destination = destination.expanduser()
    if not destination.is_absolute():
        raise ValueError("Choose an absolute path for the new data folder.")
    if destination.resolve() == settings.data_directory.resolve():
        raise ValueError("Choose a different folder from the current data folder.")
    if settings.backup_directory and destination.resolve() == settings.backup_directory.resolve():
        raise ValueError("Choose a different folder from your backup folder.")
    if destination.exists() and not destination.is_dir():
        raise ValueError(f"This is not a folder: {destination}")
    if (destination / DATABASE_NAME).exists():
        raise ValueError("The new folder already contains a Solar Forge database.")
    return destination


def queue_data_move(store: SettingsStore, settings: AppSettings, destination: Path) -> None:
    """Record a requested move; the launcher performs it on the next start."""
    destination = validate_move_target(settings, destination)
    store.save(replace(settings, pending_move_directory=destination))


def perform_pending_move(store: SettingsStore, settings: AppSettings) -> AppSettings:
    """Make and verify a SQLite snapshot, then atomically select it for future starts.

    The caller must hold the application instance lock. The source is retained.
    """
    destination_dir = settings.pending_move_directory
    if destination_dir is None:
        return settings
    source_path = settings.data_directory / DATABASE_NAME
    destination_path = destination_dir / DATABASE_NAME
    if not source_path.is_file():
        raise ValueError(f"The current database is unavailable: {source_path}")
    if destination_dir.resolve() == settings.data_directory.resolve():
        raise ValueError("The new data folder is the current data folder.")
    if destination_dir.exists() and not destination_dir.is_dir():
        raise ValueError(f"This is not a folder: {destination_dir}")
    destination_dir.mkdir(parents=True, exist_ok=True)
    if destination_path.exists():
        raise ValueError(f"The new folder already contains a database: {destination_path}")
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{DATABASE_NAME}.", suffix=".moving", dir=destination_dir
    )
    os.close(fd)
    temporary_path = Path(temporary_name)
    source_uri = f"file:{quote(str(source_path.resolve()))}?mode=ro"
    try:
        with closing(sqlite3.connect(source_uri, uri=True)) as source, closing(
            sqlite3.connect(temporary_path)
        ) as copied:
            if source.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("The current database failed its integrity check.")
            source.backup(copied)
            if copied.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("The copied database failed its integrity check.")
            if (source.execute("PRAGMA user_version").fetchone()[0]
                    != copied.execute("PRAGMA user_version").fetchone()[0]):
                raise RuntimeError("The copied database has a different schema version.")
        # A target that appeared during copying must never be overwritten.
        if destination_path.exists():
            raise ValueError(f"The new folder already contains a database: {destination_path}")
        os.link(temporary_path, destination_path)
        temporary_path.unlink()
        reopened = Storage(destination_path)
        reopened.close()
        updated = replace(settings, data_directory=destination_dir, pending_move_directory=None)
        store.save(updated)
        return updated
    finally:
        temporary_path.unlink(missing_ok=True)
