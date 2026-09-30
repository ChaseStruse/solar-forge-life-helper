"""Verified, user-owned SQLite backups kept outside the live data folder."""

import hashlib
import json
import os
import sqlite3
import tempfile
import uuid
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from urllib.parse import quote


@dataclass(frozen=True)
class BackupInfo:
    database: Path
    manifest: Path
    created_at: str
    schema_version: int
    size_bytes: int
    sha256: str


def _checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_backup(database: Path, folder: Path) -> BackupInfo:
    """Snapshot a live SQLite file, verify it, then publish it with a manifest."""
    if not database.is_file():
        raise FileNotFoundError(f"The active database is unavailable: {database}")
    folder = folder.expanduser()
    if not folder.is_absolute():
        raise ValueError("Choose an absolute backup folder.")
    if folder.resolve() == database.parent.resolve():
        raise ValueError("Choose a backup folder separate from the data folder.")
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = f"solar-forge-backup-{stamp}-{uuid.uuid4().hex[:8]}"
    published = folder / f"{name}.db"
    manifest = folder / f"{name}.json"
    fd, temporary_name = tempfile.mkstemp(prefix=f".{name}.", suffix=".tmp", dir=folder)
    os.close(fd)
    temporary = Path(temporary_name)
    manifest_temporary: Path | None = None
    published_by_us = False
    source_uri = f"file:{quote(str(database.resolve()))}?mode=ro"
    try:
        os.chmod(temporary, 0o600)
        with closing(sqlite3.connect(source_uri, uri=True)) as source, closing(
            sqlite3.connect(temporary)
        ) as snapshot:
            schema_version = source.execute("PRAGMA user_version").fetchone()[0]
            if schema_version < 1:
                raise ValueError("The active database has no supported schema version.")
            source.backup(snapshot)
            if snapshot.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("The database backup failed its integrity check.")
            if snapshot.execute("PRAGMA user_version").fetchone()[0] != schema_version:
                raise RuntimeError("The database backup has a different schema version.")
        with temporary.open("rb") as stream:
            os.fsync(stream.fileno())
        info = BackupInfo(
            published, manifest, datetime.now(timezone.utc).isoformat(),
            schema_version, temporary.stat().st_size, _checksum(temporary),
        )
        document = {
            "format_version": 1,
            "database_file": published.name,
            "created_at": info.created_at,
            "schema_version": info.schema_version,
            "size_bytes": info.size_bytes,
            "sha256": info.sha256,
            "app_version": version("solar-forge-life-desktop"),
        }
        fd, manifest_name = tempfile.mkstemp(prefix=f".{name}.", suffix=".json.tmp", dir=folder)
        manifest_temporary = Path(manifest_name)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            os.chmod(manifest_temporary, 0o600)
            json.dump(document, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, published)
        published_by_us = True
        os.replace(manifest_temporary, manifest)
        return info
    except BaseException:
        if published_by_us:
            published.unlink(missing_ok=True)
        raise
    finally:
        temporary.unlink(missing_ok=True)
        if manifest_temporary is not None:
            manifest_temporary.unlink(missing_ok=True)


def verify_backup(manifest: Path) -> BackupInfo:
    """Check that a backup and manifest still agree and the SQLite file opens cleanly."""
    document = json.loads(manifest.read_text(encoding="utf-8"))
    if document.get("format_version") != 1:
        raise ValueError("Unsupported backup manifest format.")
    name = document["database_file"]
    if Path(name).name != name or not name.endswith(".db"):
        raise ValueError("Backup manifest contains an invalid database filename.")
    database = manifest.parent / name
    if database.stat().st_size != document["size_bytes"]:
        raise ValueError("Backup file size does not match its manifest.")
    if _checksum(database) != document["sha256"]:
        raise ValueError("Backup checksum does not match its manifest.")
    uri = f"file:{quote(str(database.resolve()))}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as snapshot:
        if snapshot.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Backup database failed its integrity check.")
        if snapshot.execute("PRAGMA user_version").fetchone()[0] != document["schema_version"]:
            raise ValueError("Backup schema version does not match its manifest.")
    return BackupInfo(
        database, manifest, document["created_at"], document["schema_version"],
        document["size_bytes"], document["sha256"],
    )


def latest_backup(folder: Path) -> Path | None:
    """Return the newest manifest path, without reading or trusting its contents."""
    if not folder.is_dir():
        return None
    manifests = sorted(folder.glob("solar-forge-backup-*.json"), reverse=True)
    return manifests[0] if manifests else None
