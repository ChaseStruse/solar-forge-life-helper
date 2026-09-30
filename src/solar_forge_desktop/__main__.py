"""Manual source entry point: `uv run --frozen solar-forge-desktop`."""

import os
import sys
from pathlib import Path

from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import QApplication, QMessageBox

from solar_forge_desktop.auth import AuthService
from solar_forge_desktop.auth_window import AuthWindow
from solar_forge_desktop.paths import data_directory
from solar_forge_desktop.storage import Storage, seed_database_from_legacy
from solar_forge_desktop.tasks import TaskService
from solar_forge_desktop.window import TaskWindow


class DesktopSession:
    """Own the database and switch between the account gate and scoped workspace."""

    def __init__(self, storage: Storage):
        self.storage = storage
        self.auth = AuthService(storage)
        self.auth_window: AuthWindow | None = None
        self.task_window: TaskWindow | None = None
        self.show_auth()

    def show_auth(self) -> None:
        previous = self.task_window
        self.task_window = None
        self.auth_window = AuthWindow(self.auth, self.open_profile)
        self.auth_window.show()
        if previous is not None:
            previous.close()

    def open_profile(self, profile_id: int) -> None:
        previous = self.auth_window
        self.auth_window = None
        self.task_window = TaskWindow(
            TaskService(self.storage), profile_id, lambda: None,
            profile_name=self.storage.profile_name(profile_id), on_sign_out=self.show_auth,
        )
        self.task_window.show()
        if previous is not None:
            previous.close()


def main() -> int:
    app = QApplication(sys.argv)
    app.setOrganizationName("Solar Forge Life Helper")
    app.setApplicationName("Solar Forge Life Helper")
    try:
        data_path = data_directory() / "solar-forge-desktop.db"
        seed_database_from_legacy(data_path.with_name("luna-desktop.db"), data_path)
        legacy_override = os.environ.get("SOLAR_FORGE_DESKTOP_LEGACY_DATA_DIR")
        if legacy_override:
            legacy_path = Path(legacy_override) / "luna-desktop.db"
        elif os.environ.get("SOLAR_FORGE_DESKTOP_DATA_DIR"):
            legacy_path = None
        else:
            app.setOrganizationName("Luna Life Helper")
            app.setApplicationName("Luna Life Helper")
            old_directory = QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.AppDataLocation
            )
            app.setOrganizationName("Solar Forge Life Helper")
            app.setApplicationName("Solar Forge Life Helper")
            legacy_path = Path(old_directory) / "luna-desktop.db" if old_directory else None
        if legacy_path is not None:
            seed_database_from_legacy(legacy_path, data_path)
        storage = Storage(data_path)
    except Exception as exc:
        QMessageBox.critical(None, "Solar Forge Life Helper could not start", str(exc))
        return 1
    app.aboutToQuit.connect(storage.close)
    session = DesktopSession(storage)
    app.session = session
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
