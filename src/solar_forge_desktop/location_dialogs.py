"""First-run folder selection and recovery for a missing saved database."""

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

from solar_forge_desktop.configuration import DATABASE_NAME, AppSettings

STYLE = """
QDialog { background: #0a0712; color: #f3f4f6; }
QLabel { color: #f3f4f6; }
QLabel#hint { color: #a1a1aa; }
QLabel#error { color: #fb7185; }
QLineEdit { background: #211b39; color: #f3f4f6; border: 1px solid #39314e;
            border-radius: 8px; padding: 9px; }
QPushButton { background: #292143; color: #f3f4f6; border: 1px solid #483a64;
              border-radius: 8px; padding: 9px 13px; }
QPushButton#continue { background: #8b5cf6; border-color: #a56eff; }
"""


class StorageSetupDialog(QDialog):
    def __init__(self, data_default: Path, backup_default: Path):
        super().__init__()
        self.setWindowTitle("Solar Forge Life Helper — Choose storage")
        self.setMinimumWidth(560)
        self.setStyleSheet(STYLE)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(12)
        heading = QLabel("Choose where your data lives")
        heading.setStyleSheet("font-size: 22px; font-weight: 700;")
        layout.addWidget(heading)
        hint = QLabel(
            "Your family data stays in a local SQLite file. Choose a separate folder for "
            "future backups. You can use the suggested locations."
        )
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.data_input = self._folder_row(layout, "Data folder", data_default)
        self.backup_input = self._folder_row(layout, "Backup folder", backup_default)
        backup_note = QLabel(
            "Automatic backups use this folder when a schedule is enabled in Settings."
        )
        backup_note.setObjectName("hint")
        backup_note.setWordWrap(True)
        layout.addWidget(backup_note)
        self.error = QLabel("")
        self.error.setObjectName("error")
        self.error.setWordWrap(True)
        layout.addWidget(self.error)
        actions = QHBoxLayout()
        actions.addStretch()
        cancel = QPushButton("Quit")
        cancel.clicked.connect(self.reject)
        actions.addWidget(cancel)
        self.continue_button = QPushButton("Continue")
        self.continue_button.setObjectName("continue")
        self.continue_button.clicked.connect(self.accept)
        actions.addWidget(self.continue_button)
        layout.addLayout(actions)

    def _folder_row(self, layout: QVBoxLayout, label: str, default: Path) -> QLineEdit:
        layout.addWidget(QLabel(label))
        row = QHBoxLayout()
        field = QLineEdit(str(default))
        field.setAccessibleName(label)
        row.addWidget(field)
        browse = QPushButton("Browse…")
        browse.clicked.connect(lambda: self._browse(field))
        row.addWidget(browse)
        layout.addLayout(row)
        return field

    def _browse(self, field: QLineEdit) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose folder", field.text())
        if folder:
            field.setText(folder)

    def selected_settings(self) -> AppSettings:
        data = Path(self.data_input.text().strip()).expanduser()
        backup = Path(self.backup_input.text().strip()).expanduser()
        if not data.is_absolute() or not backup.is_absolute():
            raise ValueError("Choose absolute paths for both folders.")
        if data.resolve() == backup.resolve():
            raise ValueError("Choose a different folder for backups.")
        for path in (data, backup):
            if path.exists() and not path.is_dir():
                raise ValueError(f"This is not a folder: {path}")
        return AppSettings(data, backup)

    def accept(self) -> None:
        try:
            self.selected_settings()
        except ValueError as exc:
            self.error.setText(str(exc))
            return
        super().accept()


def locate_existing_database(missing: Path) -> Path | None:
    """Offer retry or a different existing folder without creating a new database."""
    while True:
        box = QMessageBox()
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Solar Forge Life Helper — Data unavailable")
        box.setText("Your selected data folder is unavailable.")
        box.setInformativeText(
            f"Expected {DATABASE_NAME} in:\n{missing}\n\n"
            "Reconnect the drive and retry, or locate the existing data folder."
        )
        retry = box.addButton("Retry", QMessageBox.ButtonRole.AcceptRole)
        locate = box.addButton("Locate data…", QMessageBox.ButtonRole.ActionRole)
        box.addButton("Quit", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is retry:
            return missing
        if box.clickedButton() is not locate:
            return None
        folder = QFileDialog.getExistingDirectory(None, "Locate existing data folder", str(missing))
        if not folder:
            continue
        selected = Path(folder)
        if (selected / DATABASE_NAME).is_file():
            return selected
        QMessageBox.warning(None, "Database not found", f"No {DATABASE_NAME} was found there.")
