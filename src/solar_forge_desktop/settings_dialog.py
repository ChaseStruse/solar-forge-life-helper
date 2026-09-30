"""User-facing storage preferences for the current desktop session."""

import os
from dataclasses import replace
from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from solar_forge_desktop.backup_scheduler import BackupScheduler
from solar_forge_desktop.backups import (
    BackupInfo,
    create_backup,
    latest_backup,
    next_backup_due,
    prune_backups,
    verify_backup,
)
from solar_forge_desktop.configuration import DATABASE_NAME, AppSettings, SettingsStore
from solar_forge_desktop.data_move import validate_move_target
from solar_forge_desktop.location_dialogs import STYLE
from solar_forge_desktop.paths import default_backup_directory
from solar_forge_desktop.restore import queue_restore
from solar_forge_desktop.workers import BackgroundWorker


def save_storage_locations(
    store: SettingsStore, data_directory: Path, chosen_data: Path, backup: Path,
    can_change_data: bool, schedule: str | None = None, retention: int | None = None,
) -> bool:
    """Save both locations; queue a verified move when the data path changes."""
    current = store.load()
    selected_data = current.data_directory if current else data_directory
    chosen_data = chosen_data.expanduser()
    if not chosen_data.is_absolute():
        raise ValueError("Choose an absolute path for the data folder.")
    changing_data = chosen_data.resolve() != data_directory.resolve()
    if changing_data and not can_change_data:
        raise ValueError("The data folder is controlled by the launcher.")
    pending = current.pending_move_directory if current else None
    if changing_data:
        pending = validate_move_target(
            AppSettings(selected_data, backup), chosen_data
        )
    backup = backup.expanduser()
    if not backup.is_absolute():
        raise ValueError("Choose an absolute path for the backup folder.")
    if backup.resolve() == data_directory.resolve():
        raise ValueError("Choose a different folder from your data folder.")
    if pending and backup.resolve() == pending.resolve():
        raise ValueError("Choose a different folder from your planned data folder.")
    if backup.exists() and not backup.is_dir():
        raise ValueError(f"This is not a folder: {backup}")
    backup.mkdir(parents=True, exist_ok=True)
    base = current or AppSettings(selected_data)
    store.save(replace(
        base, data_directory=selected_data, backup_directory=backup,
        pending_move_directory=pending,
        backup_schedule=schedule if schedule is not None else base.backup_schedule,
        backup_retention=retention if retention is not None else base.backup_retention,
    ))
    return changing_data


def save_backup_directory(store: SettingsStore, data_directory: Path, backup: Path) -> None:
    """Keep the backup-only API for callers that do not offer data relocation."""
    save_storage_locations(store, data_directory, data_directory, backup, False)


class StorageSettingsDialog(QDialog):
    def __init__(
        self, store: SettingsStore, data_directory: Path, parent=None,
        scheduler: BackupScheduler | None = None,
    ):
        super().__init__(parent)
        self.store = store
        self.data_directory = data_directory
        self.scheduler = scheduler
        self._busy = False
        self.can_change_data = not bool(os.environ.get("SOLAR_FORGE_DESKTOP_DATA_DIR"))
        self._worker = BackgroundWorker(self, "solar-forge-backup")
        self._worker.busy_changed.connect(self._set_busy)
        self._worker.failed.connect(self._backup_failed)
        self.finished.connect(lambda _result: self._worker.shutdown())
        self.setWindowTitle("Storage settings")
        self.setMinimumWidth(560)
        self.setStyleSheet(STYLE + """
            QComboBox, QSpinBox { background: #211b39; color: #f3f4f6;
                border: 1px solid #39314e; border-radius: 8px; padding: 9px; }
            QComboBox QAbstractItemView { background: #211b39; color: #f3f4f6;
                selection-background-color: #8b5cf6; }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(12)
        heading = QLabel("Storage settings")
        heading.setStyleSheet("font-size: 22px; font-weight: 700;")
        layout.addWidget(heading)
        layout.addWidget(QLabel("Data folder"))
        data_row = QHBoxLayout()
        self.data_input = QLineEdit(str(data_directory))
        self.data_input.setAccessibleName("Data folder")
        self.data_input.setReadOnly(not self.can_change_data)
        data_row.addWidget(self.data_input)
        if self.can_change_data:
            browse_data = QPushButton("Browse…")
            browse_data.clicked.connect(self._browse_data)
            data_row.addWidget(browse_data)
        layout.addLayout(data_row)
        hint = QLabel(
            "Change this folder to copy and verify your database on the next launch. "
            "The original is kept."
            if self.can_change_data else
            "This folder is set by Docker Compose or another launcher."
        )
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        if self.can_change_data and (saved := store.load()):
            if saved.pending_move_directory:
                pending_note = QLabel(
                    f"Move planned for next launch: {saved.pending_move_directory}"
                )
                pending_note.setObjectName("hint")
                pending_note.setWordWrap(True)
                layout.addWidget(pending_note)
        layout.addWidget(QLabel("Backup folder"))
        row = QHBoxLayout()
        saved = store.load()
        backup = (
            saved.backup_directory
            if saved and saved.backup_directory else default_backup_directory()
        )
        self.backup_input = QLineEdit(str(backup))
        self.backup_input.setAccessibleName("Backup folder")
        row.addWidget(self.backup_input)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        row.addWidget(browse)
        layout.addLayout(row)
        note = QLabel(
            "Backups are local and unencrypted. A cloud-synced folder may upload them. "
            "Scheduled backups run while this app is open."
        )
        note.setObjectName("hint")
        note.setWordWrap(True)
        layout.addWidget(note)
        schedule_row = QHBoxLayout()
        schedule_row.addWidget(QLabel("Automatic backups"))
        self.schedule_input = QComboBox()
        for label, value in (("Off", "off"), ("Daily", "daily"), ("Weekly", "weekly")):
            self.schedule_input.addItem(label, value)
        self.schedule_input.setCurrentIndex(
            self.schedule_input.findData(saved.backup_schedule if saved else "off")
        )
        schedule_row.addWidget(self.schedule_input)
        schedule_row.addWidget(QLabel("Keep"))
        self.retention_input = QSpinBox()
        self.retention_input.setRange(1, 30)
        self.retention_input.setValue(saved.backup_retention if saved else 7)
        self.retention_input.setSuffix(" backups")
        schedule_row.addWidget(self.retention_input)
        layout.addLayout(schedule_row)
        self.next_backup_label = QLabel()
        self.next_backup_label.setObjectName("hint")
        layout.addWidget(self.next_backup_label)
        self.schedule_input.currentIndexChanged.connect(self._show_next_backup)
        backup_actions = QHBoxLayout()
        self.backup_button = QPushButton("Back up now")
        self.backup_button.clicked.connect(self._start_backup)
        backup_actions.addWidget(self.backup_button)
        self.verify_button = QPushButton("Verify latest")
        self.verify_button.clicked.connect(self._verify_latest)
        backup_actions.addWidget(self.verify_button)
        backup_actions.addStretch()
        layout.addLayout(backup_actions)
        self.backup_status = QLabel()
        self.backup_status.setObjectName("hint")
        self.backup_status.setWordWrap(True)
        layout.addWidget(self.backup_status)
        self._show_latest()
        self._show_next_backup()
        if scheduler is not None:
            scheduler.status_changed.connect(self.backup_status.setText)
        layout.addWidget(QLabel("Restore from backup"))
        restore_row = QHBoxLayout()
        self.restore_input = QComboBox()
        self.restore_input.setAccessibleName("Backup to restore")
        restore_row.addWidget(self.restore_input, 1)
        self.restore_button = QPushButton("Restore…")
        self.restore_button.clicked.connect(self._start_restore)
        restore_row.addWidget(self.restore_button)
        layout.addLayout(restore_row)
        self.backup_input.textChanged.connect(self._refresh_restore_options)
        self._refresh_restore_options()
        actions = QHBoxLayout()
        actions.addStretch()
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        actions.addWidget(self.cancel_button)
        self.save_button = QPushButton("Save")
        self.save_button.setObjectName("continue")
        self.save_button.clicked.connect(self.accept)
        actions.addWidget(self.save_button)
        layout.addLayout(actions)

    def _show_latest(self) -> None:
        manifest = latest_backup(Path(self.backup_input.text().strip()).expanduser())
        self.backup_status.setText(
            f"Latest backup: {manifest.name}"
            if manifest else "No manual backups in this folder yet."
        )
        if self.scheduler is not None and self.scheduler.last_result:
            self.backup_status.setText(self.scheduler.last_result)

    def _show_next_backup(self) -> None:
        due = next_backup_due(
            Path(self.backup_input.text().strip()).expanduser(),
            self.schedule_input.currentData(),
        )
        if due is None:
            self.next_backup_label.setText("Automatic backups are off.")
        else:
            self.next_backup_label.setText(
                f"Next backup while the app is open: {due.astimezone():%b %d, %Y %I:%M %p}"
            )

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        for button in (
            self.backup_button, self.verify_button, self.save_button, self.cancel_button,
            self.restore_button,
        ):
            button.setEnabled(not busy)
        if not busy:
            self.restore_button.setEnabled(self.restore_input.currentData() is not None)

    def _backup_failed(self, error: Exception) -> None:
        self.backup_status.setText(f"Backup check failed: {error}")

    def _backup_done(self, result: tuple[BackupInfo, str | None]) -> None:
        info, cleanup_error = result
        message = f"Backup saved and verified: {info.database}"
        if cleanup_error:
            message += f". Older backups could not be removed: {cleanup_error}"
        self.backup_status.setText(message)
        self._show_next_backup()
        self._refresh_restore_options()

    def _start_backup(self) -> None:
        folder = Path(self.backup_input.text().strip())
        try:
            save_backup_directory(self.store, self.data_directory, folder)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Could not choose backup folder", str(exc))
            return
        self.backup_status.setText("Creating and verifying backup…")
        keep = self.retention_input.value()

        def action() -> tuple[BackupInfo, str | None]:
            info = create_backup(self.data_directory / DATABASE_NAME, folder)
            try:
                prune_backups(info.database.parent, keep)
            except Exception as exc:
                return info, str(exc)
            return info, None

        self._worker.submit(
            action, self._backup_done,
        )

    def _verify_latest(self) -> None:
        folder = Path(self.backup_input.text().strip()).expanduser()
        manifest = latest_backup(folder)
        if manifest is None:
            self.backup_status.setText("No manual backups in this folder yet.")
            return
        self.backup_status.setText("Verifying latest backup…")
        self._worker.submit(lambda: verify_backup(manifest), self._verified)

    def _verified(self, info: BackupInfo) -> None:
        self.backup_status.setText(f"Backup verified: {info.database}")

    def _refresh_restore_options(self) -> None:
        self.restore_input.clear()
        folder = Path(self.backup_input.text().strip()).expanduser()
        if folder.is_dir():
            for manifest in sorted(folder.glob("solar-forge-backup-*.json"), reverse=True):
                self.restore_input.addItem(manifest.name, manifest)
        if self.restore_input.count() == 0:
            self.restore_input.addItem("No backups available", None)
        self.restore_button.setEnabled(
            self.restore_input.currentData() is not None and not self._busy
        )

    def _start_restore(self) -> None:
        manifest = self.restore_input.currentData()
        if manifest is None:
            return
        answer = QMessageBox.question(
            self, "Restore backup on next launch?",
            f"Restore {manifest.name}?\n\n"
            "This will replace the current database on the next launch. "
            "A separate recovery copy of the current database will be kept.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            save_backup_directory(
                self.store, self.data_directory, Path(self.backup_input.text().strip())
            )
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Could not choose backup folder", str(exc))
            return
        self.backup_status.setText("Verifying backup before planning restore…")
        self._worker.submit(lambda: verify_backup(manifest), self._queue_verified_restore)

    def _queue_verified_restore(self, info: BackupInfo) -> None:
        try:
            settings = self.store.load()
            queue_restore(self.store, settings, info.manifest, verified=info)
        except (OSError, ValueError) as exc:
            self.backup_status.setText(f"Restore could not be planned: {exc}")
            return
        QMessageBox.information(
            self, "Restore planned",
            "Close and reopen Solar Forge Life Helper to restore this backup. "
            "The current database will be saved separately for recovery.",
        )
        self.reject()

    def _browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Choose backup folder", self.backup_input.text()
        )
        if folder:
            self.backup_input.setText(folder)

    def _browse_data(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Choose data folder", self.data_input.text()
        )
        if folder:
            self.data_input.setText(folder)

    def accept(self) -> None:
        try:
            changing_data = save_storage_locations(
                self.store, self.data_directory, Path(self.data_input.text().strip()),
                Path(self.backup_input.text().strip()), self.can_change_data,
                self.schedule_input.currentData(), self.retention_input.value(),
            )
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Could not save storage folders", str(exc))
            return
        super().accept()
        if self.scheduler is not None:
            self.scheduler.check()
        if changing_data:
            QMessageBox.information(
                self.parentWidget(), "Data move planned",
                "Close and reopen Solar Forge Life Helper to copy and verify your database. "
                "The original will remain in its current folder.",
            )
