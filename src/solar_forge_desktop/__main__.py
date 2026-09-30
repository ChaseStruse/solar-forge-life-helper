"""Manual source entry point: `uv run --frozen solar-forge-desktop`."""

import os
import sys
from pathlib import Path

from PySide6.QtCore import QLockFile
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from solar_forge_desktop.auth import AuthService
from solar_forge_desktop.auth_window import AuthWindow
from solar_forge_desktop.bootstrap import import_legacy_database
from solar_forge_desktop.configuration import (
    DATABASE_NAME,
    AppSettings,
    DataLocationUnavailable,
    SettingsStore,
    resolve_data_directory,
)
from solar_forge_desktop.data_move import perform_pending_move
from solar_forge_desktop.location_dialogs import StorageSetupDialog, locate_existing_database
from solar_forge_desktop.paths import (
    configuration_directory,
    default_backup_directory,
    default_data_directory,
)
from solar_forge_desktop.storage import Storage
from solar_forge_desktop.tasks import TaskService
from solar_forge_desktop.window import TaskWindow


class DesktopSession:
    """Own the database and switch between the account gate and scoped workspace."""

    def __init__(
        self, storage: Storage, store: SettingsStore | None = None,
        data_directory: Path | None = None,
    ):
        self.storage = storage
        self.store = store
        self.data_directory = data_directory
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
            settings_store=self.store, data_directory=self.data_directory,
        )
        self.task_window.show()
        if previous is not None:
            previous.close()


def main() -> int:
    app = QApplication(sys.argv)
    app.setOrganizationName("Solar Forge Life Helper")
    app.setApplicationName("Solar Forge Life Helper")
    try:
        config_dir = configuration_directory()
        config_dir.mkdir(parents=True, exist_ok=True)
        instance_lock = QLockFile(str(config_dir / "app.lock"))
        if not instance_lock.tryLock(0):
            QMessageBox.warning(
                None, "Solar Forge Life Helper is already open",
                "Close the other instance before opening this one.",
            )
            return 1
        store = SettingsStore(config_dir)
        settings = store.load()
        default = default_data_directory()
        has_override = bool(os.environ.get("SOLAR_FORGE_DESKTOP_DATA_DIR"))
        if settings is not None and settings.pending_move_directory and not has_override:
            try:
                settings = perform_pending_move(store, settings)
            except Exception as exc:
                QMessageBox.warning(
                    None, "Data move could not finish",
                    f"Your original database has not been removed.\n\n{exc}",
                )
                settings = AppSettings(settings.data_directory, settings.backup_directory)
                store.save(settings)
        save_choice = False
        new_setup = False
        if settings is None and not has_override and not (default / DATABASE_NAME).is_file():
            setup = StorageSetupDialog(default, default_backup_directory())
            if setup.exec() != QDialog.DialogCode.Accepted:
                return 0
            settings = setup.selected_settings()
            settings.backup_directory.mkdir(parents=True, exist_ok=True)
            save_choice = new_setup = True
        while True:
            try:
                directory = (settings.data_directory if new_setup else
                             resolve_data_directory(settings, default, os.environ))
                break
            except DataLocationUnavailable:
                replacement = locate_existing_database(settings.data_directory)
                if replacement is None:
                    return 1
                settings = AppSettings(replacement, settings.backup_directory)
                save_choice = True
        data_path = directory / DATABASE_NAME
        import_legacy_database(app, data_path)
        storage = Storage(data_path)
        if (save_choice or (settings is None and not has_override)) and not has_override:
            store.save(settings or AppSettings(directory))
    except Exception as exc:
        QMessageBox.critical(None, "Solar Forge Life Helper could not start", str(exc))
        return 1
    app.aboutToQuit.connect(storage.close)
    session = DesktopSession(storage, store, directory)
    app.session = session
    result = app.exec()
    instance_lock.unlock()
    return result


if __name__ == "__main__":
    raise SystemExit(main())
