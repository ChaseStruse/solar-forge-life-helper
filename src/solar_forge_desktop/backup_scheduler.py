"""Run opt-in backups while the desktop application is open."""

from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

from solar_forge_desktop.backups import (
    BackupInfo,
    create_backup,
    next_backup_due,
    prune_backups,
)
from solar_forge_desktop.configuration import DATABASE_NAME, SettingsStore
from solar_forge_desktop.workers import BackgroundWorker


class BackupScheduler(QObject):
    status_changed = Signal(str)

    def __init__(self, store: SettingsStore, data_directory: Path, parent: QObject):
        super().__init__(parent)
        self.store = store
        self.database = data_directory / DATABASE_NAME
        self.last_result: str | None = None
        self._busy = False
        self._worker = BackgroundWorker(self, "solar-forge-scheduled-backup")
        self._worker.busy_changed.connect(self._set_busy)
        self._worker.failed.connect(self._failed)
        self._timer = QTimer(self)
        self._timer.setInterval(15 * 60 * 1000)
        self._timer.timeout.connect(self.check)

    def start(self) -> None:
        self._timer.start()
        QTimer.singleShot(0, self.check)

    def check(self) -> None:
        if self._busy:
            return
        try:
            settings = self.store.load()
            if settings is None or settings.backup_directory is None:
                return
            due = next_backup_due(settings.backup_directory, settings.backup_schedule)
            if due is None or due > datetime.now(timezone.utc):
                return
            folder = settings.backup_directory
            keep = settings.backup_retention
        except Exception as exc:
            self._failed(exc)
            return

        def action() -> tuple[BackupInfo, str | None]:
            info = create_backup(self.database, folder)
            try:
                prune_backups(folder, keep)
            except Exception as exc:
                return info, str(exc)
            return info, None

        self._worker.submit(action, self._completed)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy

    def _failed(self, error: Exception) -> None:
        self.last_result = f"Scheduled backup failed: {error}"
        self.status_changed.emit(self.last_result)

    def _completed(self, result: tuple[BackupInfo, str | None]) -> None:
        info, cleanup_error = result
        self.last_result = f"Scheduled backup saved: {info.database}"
        if cleanup_error:
            self.last_result += f". Older backups could not be removed: {cleanup_error}"
        self.status_changed.emit(self.last_result)

    def shutdown(self) -> None:
        self._timer.stop()
        self._worker.shutdown()
