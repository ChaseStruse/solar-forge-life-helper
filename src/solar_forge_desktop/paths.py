"""Resolve standard application folders and explicit environment overrides."""

import os
from pathlib import Path

from PySide6.QtCore import QStandardPaths


def data_directory() -> Path:
    override = os.environ.get("SOLAR_FORGE_DESKTOP_DATA_DIR")
    if override:
        location = Path(override).expanduser()
        if not location.is_absolute():
            raise ValueError("SOLAR_FORGE_DESKTOP_DATA_DIR must be an absolute path.")
        return location
    return default_data_directory()


def default_data_directory() -> Path:
    location = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    if not location:
        raise RuntimeError("The operating system did not provide an application data directory.")
    return Path(location)


def configuration_directory() -> Path:
    override = os.environ.get("SOLAR_FORGE_DESKTOP_CONFIG_DIR")
    if override:
        location = Path(override).expanduser()
        if not location.is_absolute():
            raise ValueError("SOLAR_FORGE_DESKTOP_CONFIG_DIR must be an absolute path.")
        return location
    location = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation)
    if not location:
        raise RuntimeError("The operating system did not provide an application config directory.")
    return Path(location)


def default_backup_directory() -> Path:
    override = os.environ.get("SOLAR_FORGE_DESKTOP_BACKUP_DIR")
    if override:
        location = Path(override).expanduser()
        if not location.is_absolute():
            raise ValueError("SOLAR_FORGE_DESKTOP_BACKUP_DIR must be an absolute path.")
        return location
    location = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
    return Path(location or Path.home()) / "Solar Forge Life Helper Backups"
