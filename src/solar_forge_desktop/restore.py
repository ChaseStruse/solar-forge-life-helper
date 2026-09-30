"""Restore a verified backup before the desktop opens its database."""

import hashlib
import os
import shutil
import sqlite3
import tempfile
from contextlib import closing
from dataclasses import replace
from pathlib import Path
from urllib.parse import quote

from solar_forge_desktop.backups import BackupInfo, create_backup, verify_backup
from solar_forge_desktop.configuration import DATABASE_NAME, AppSettings, SettingsStore
from solar_forge_desktop.storage import Storage


class RestoreRollbackFailed(RuntimeError):
    """The original database could not be reopened after a failed restore."""


def queue_restore(
    store: SettingsStore, settings: AppSettings, manifest: Path,
    verified: BackupInfo | None = None,
) -> BackupInfo:
    if settings.pending_move_directory is not None:
        raise ValueError("Finish the planned data move before restoring a backup.")
    if settings.backup_directory is None:
        raise ValueError("Choose a backup folder before restoring.")
    manifest = manifest.expanduser().resolve()
    if manifest.parent != settings.backup_directory.resolve():
        raise ValueError("Choose a backup from your selected backup folder.")
    info = verified if verified and verified.manifest == manifest else verify_backup(manifest)
    if not 1 <= info.schema_version <= 14:
        raise ValueError("This backup uses an unsupported database version.")
    store.save(replace(settings, pending_restore_manifest=manifest))
    return info


def _copy_verified(source: Path, destination: Path, checksum: str) -> None:
    with source.open("rb") as original, destination.open("wb") as copied:
        os.chmod(destination, 0o600)
        shutil.copyfileobj(original, copied, 1024 * 1024)
        copied.flush()
        os.fsync(copied.fileno())
    with destination.open("rb") as copied:
        if hashlib.file_digest(copied, "sha256").hexdigest() != checksum:
            raise ValueError("The database copy did not match the verified backup.")
    uri = f"file:{quote(str(destination.resolve()))}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as database:
        if database.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("The database copy failed its integrity check.")


def _remove_sidecars(database: Path) -> None:
    for suffix in ("-wal", "-shm", "-journal"):
        sidecar = Path(str(database) + suffix)
        if sidecar.exists():
            sidecar.unlink()


def perform_pending_restore(
    store: SettingsStore, settings: AppSettings, data_directory: Path,
) -> BackupInfo | None:
    """Swap in a verified copy, preserving the former database for recovery."""
    manifest = settings.pending_restore_manifest
    if manifest is None:
        return None
    if settings.backup_directory is None:
        raise ValueError("The selected backup folder is missing.")
    if manifest.resolve().parent != settings.backup_directory.resolve():
        raise ValueError("The selected backup is outside the backup folder.")
    info = verify_backup(manifest)
    if not 1 <= info.schema_version <= 14:
        raise ValueError("This backup uses an unsupported database version.")
    current = data_directory / DATABASE_NAME
    if not current.is_file():
        raise FileNotFoundError(f"The current database is unavailable: {current}")
    with closing(sqlite3.connect(current)) as database:
        database.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    safety = create_backup(current, settings.backup_directory, kind="pre-restore")
    fd, temporary_name = tempfile.mkstemp(prefix=".restore-", dir=current.parent)
    os.close(fd)
    temporary = Path(temporary_name)
    replaced = False
    try:
        os.chmod(temporary, 0o600)
        _copy_verified(info.database, temporary, info.sha256)
        _remove_sidecars(current)
        os.replace(temporary, current)
        replaced = True
        reopened = Storage(current)
        reopened.close()
        store.save(replace(settings, pending_restore_manifest=None))
        return safety
    except BaseException as exc:
        if replaced:
            try:
                _copy_verified(safety.database, temporary, safety.sha256)
                _remove_sidecars(current)
                os.replace(temporary, current)
                reopened = Storage(current)
                reopened.close()
            except BaseException as rollback_error:
                raise RestoreRollbackFailed(
                    f"Restore failed and the original could not be reopened. "
                    f"Recovery copy: {safety.database}. Error: {rollback_error}"
                ) from exc
        raise
    finally:
        temporary.unlink(missing_ok=True)
