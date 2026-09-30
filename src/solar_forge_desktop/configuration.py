"""Small, database-independent settings for locating user-owned data."""

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

DATABASE_NAME = "solar-forge-desktop.db"
SETTINGS_NAME = "settings.json"


class DataLocationUnavailable(RuntimeError):
    """A saved database location is missing and must not be recreated silently."""


@dataclass(frozen=True)
class AppSettings:
    data_directory: Path
    backup_directory: Path | None = None


def _absolute_directory(value: str | Path, label: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise ValueError(f"{label} must be an absolute path.")
    return path


class SettingsStore:
    def __init__(self, directory: Path):
        self.path = directory / SETTINGS_NAME

    def load(self) -> AppSettings | None:
        if not self.path.exists():
            return None
        try:
            document = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(document, dict) or document.get("version") != 1:
                raise ValueError("Unsupported settings format.")
            data = _absolute_directory(document["data_directory"], "Data location")
            backup_value = document.get("backup_directory")
            backup = (_absolute_directory(backup_value, "Backup location")
                      if backup_value is not None else None)
            return AppSettings(data, backup)
        except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
            raise ValueError(f"Could not read application settings: {self.path}") from exc

    def save(self, settings: AppSettings) -> None:
        data = _absolute_directory(settings.data_directory, "Data location")
        backup = (_absolute_directory(settings.backup_directory, "Backup location")
                  if settings.backup_directory is not None else None)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(prefix=".settings-", dir=self.path.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                os.chmod(temporary, 0o600)
                json.dump({"version": 1, "data_directory": str(data),
                           "backup_directory": str(backup) if backup else None}, stream)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)


def resolve_data_directory(
    settings: AppSettings | None, default: Path, environment: Mapping[str, str],
) -> Path:
    override = environment.get("SOLAR_FORGE_DESKTOP_DATA_DIR")
    if override:
        return _absolute_directory(override, "SOLAR_FORGE_DESKTOP_DATA_DIR")
    if settings is None:
        return default
    directory = settings.data_directory
    database = directory / DATABASE_NAME
    if not directory.is_dir() or not database.is_file():
        raise DataLocationUnavailable(
            f"The selected database is unavailable: {database}. "
            "Reconnect its drive or locate the existing data folder."
        )
    return directory
