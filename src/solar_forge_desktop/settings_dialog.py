"""User-facing storage preferences for the current desktop session."""

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
from solar_forge_desktop.location_dialogs import STYLE
from solar_forge_desktop.paths import default_backup_directory


def save_backup_directory(store: SettingsStore, data_directory: Path, backup: Path) -> None:
    """Validate a future backup location without changing the active database."""
    backup = backup.expanduser()
    if not backup.is_absolute():
        raise ValueError("Choose an absolute path for the backup folder.")
    if backup.resolve() == data_directory.resolve():
        raise ValueError("Choose a different folder from your data folder.")
    if backup.exists() and not backup.is_dir():
        raise ValueError(f"This is not a folder: {backup}")
    backup.mkdir(parents=True, exist_ok=True)
    store.save(AppSettings(data_directory, backup))


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
        hint = QLabel("Your SQLite database is in this folder. Moving it safely is coming next.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)
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

    def accept(self) -> None:
        try:
            save_backup_directory(
                self.store, self.data_directory, Path(self.backup_input.text().strip())
            )
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Could not save backup folder", str(exc))
            return
        super().accept()
