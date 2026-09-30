"""Choose the desktop's own data directory without touching the Flask database."""

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
    location = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    if not location:
        raise RuntimeError("The operating system did not provide an application data directory.")
    return Path(location)
