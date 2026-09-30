"""User-facing storage preferences for the current desktop session."""

import os
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from solar_forge_desktop.configuration import AppSettings, SettingsStore
from solar_forge_desktop.data_move import queue_data_move
from solar_forge_desktop.location_dialogs import STYLE
from solar_forge_desktop.paths import default_backup_directory


def save_backup_directory(store: SettingsStore, data_directory: Path, backup: Path) -> None:
    """Validate a future backup location without changing the active database."""
    backup = backup.expanduser()
    if not backup.is_absolute():
        raise ValueError("Choose an absolute path for the backup folder.")
    if backup.resolve() == data_directory.resolve():
        raise ValueError("Choose a different folder from your data folder.")
    current = store.load()
    if (
        current and current.pending_move_directory
        and backup.resolve() == current.pending_move_directory.resolve()
    ):
        raise ValueError("Choose a different folder from your planned data folder.")
    if backup.exists() and not backup.is_dir():
        raise ValueError(f"This is not a folder: {backup}")
    backup.mkdir(parents=True, exist_ok=True)
    pending = current.pending_move_directory if current else None
    selected_data = current.data_directory if current else data_directory
    store.save(AppSettings(selected_data, backup, pending))


class StorageSettingsDialog(QDialog):
    def __init__(self, store: SettingsStore, data_directory: Path, parent=None):
        super().__init__(parent)
        self.store = store
        self.data_directory = data_directory
        self.setWindowTitle("Storage settings")
        self.setMinimumWidth(560)
        self.setStyleSheet(STYLE)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(12)
        heading = QLabel("Storage settings")
        heading.setStyleSheet("font-size: 22px; font-weight: 700;")
        layout.addWidget(heading)
        layout.addWidget(QLabel("Current data folder"))
        self.data_input = QLineEdit(str(data_directory))
        self.data_input.setAccessibleName("Current data folder")
        self.data_input.setReadOnly(True)
        layout.addWidget(self.data_input)
        hint = QLabel("Your SQLite database is in this folder.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        if not os.environ.get("SOLAR_FORGE_DESKTOP_DATA_DIR"):
            move = QPushButton("Move data…")
            move.clicked.connect(self._queue_move)
            layout.addWidget(move)
            if saved := store.load():
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
        note = QLabel("Automatic backups are not available yet. This saves the folder for them.")
        note.setObjectName("hint")
        note.setWordWrap(True)
        layout.addWidget(note)
        actions = QHBoxLayout()
        actions.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        actions.addWidget(cancel)
        save = QPushButton("Save")
        save.setObjectName("continue")
        save.clicked.connect(self.accept)
        actions.addWidget(save)
        layout.addLayout(actions)

    def _browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Choose backup folder", self.backup_input.text()
        )
        if folder:
            self.backup_input.setText(folder)

    def _queue_move(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Choose new data folder", str(self.data_directory)
        )
        if not folder:
            return
        try:
            current = self.store.load() or AppSettings(self.data_directory)
            queue_data_move(self.store, current, Path(folder))
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Could not plan data move", str(exc))
            return
        QMessageBox.information(
            self, "Data move planned",
            "Close and reopen Solar Forge Life Helper to copy and verify your database. "
            "The original will remain in its current folder.",
        )
        self.reject()

    def accept(self) -> None:
        try:
            save_backup_directory(
                self.store, self.data_directory, Path(self.backup_input.text().strip())
            )
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Could not save backup folder", str(exc))
            return
        super().accept()
