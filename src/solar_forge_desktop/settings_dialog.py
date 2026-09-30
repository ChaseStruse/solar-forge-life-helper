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
from solar_forge_desktop.data_move import validate_move_target
from solar_forge_desktop.location_dialogs import STYLE
from solar_forge_desktop.paths import default_backup_directory


def save_storage_locations(
    store: SettingsStore, data_directory: Path, chosen_data: Path, backup: Path,
    can_change_data: bool,
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
    store.save(AppSettings(selected_data, backup, pending))
    return changing_data


def save_backup_directory(store: SettingsStore, data_directory: Path, backup: Path) -> None:
    """Keep the backup-only API for callers that do not offer data relocation."""
    save_storage_locations(store, data_directory, data_directory, backup, False)


class StorageSettingsDialog(QDialog):
    def __init__(self, store: SettingsStore, data_directory: Path, parent=None):
        super().__init__(parent)
        self.store = store
        self.data_directory = data_directory
        self.can_change_data = not bool(os.environ.get("SOLAR_FORGE_DESKTOP_DATA_DIR"))
        self.setWindowTitle("Storage settings")
        self.setMinimumWidth(560)
        self.setStyleSheet(STYLE)
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
            )
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Could not save storage folders", str(exc))
            return
        super().accept()
        if changing_data:
            QMessageBox.information(
                self.parentWidget(), "Data move planned",
                "Close and reopen Solar Forge Life Helper to copy and verify your database. "
                "The original will remain in its current folder.",
            )
