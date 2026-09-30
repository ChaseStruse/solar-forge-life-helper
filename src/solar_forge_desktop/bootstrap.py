"""Import supported older data before opening the selected SQLite database."""

import os
from pathlib import Path
from typing import Mapping

from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import QApplication

from solar_forge_desktop.storage import seed_database_from_legacy


def import_previous_database(
    destination: Path, environment: Mapping[str, str] = os.environ,
) -> None:
    """Copy a former Compose data mount when switching to a host folder."""
    previous = environment.get("SOLAR_FORGE_DESKTOP_PREVIOUS_DATA_DIR")
    if previous and not destination.exists():
        for name in (destination.name, "luna-desktop.db"):
            if seed_database_from_legacy(Path(previous) / name, destination):
                break


def _former_application_data_directory(app: QApplication) -> Path | None:
    organization, application = app.organizationName(), app.applicationName()
    try:
        app.setOrganizationName("Luna Life Helper")
        app.setApplicationName("Luna Life Helper")
        location = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
        return Path(location) if location else None
    finally:
        app.setOrganizationName(organization)
        app.setApplicationName(application)


def import_legacy_database(
    app: QApplication, destination: Path, environment: Mapping[str, str] = os.environ,
) -> None:
    sources = [destination.with_name("luna-desktop.db")]
    override = environment.get("SOLAR_FORGE_DESKTOP_LEGACY_DATA_DIR")
    if override:
        sources.append(Path(override).expanduser() / "luna-desktop.db")
    elif not environment.get("SOLAR_FORGE_DESKTOP_DATA_DIR"):
        former = _former_application_data_directory(app)
        if former is not None:
            sources.append(former / "luna-desktop.db")
    for source in sources:
        if seed_database_from_legacy(source, destination):
            break
