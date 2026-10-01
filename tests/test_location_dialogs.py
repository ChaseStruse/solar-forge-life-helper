"""The first-run picker validates paths before the database is opened."""

from pathlib import Path

from PySide6.QtWidgets import QDialog

from solar_forge_desktop.location_dialogs import StorageSetupDialog


def test_storage_setup_requires_distinct_absolute_folders(qtbot, tmp_path: Path) -> None:
    data = tmp_path / "data"
    backup = tmp_path / "backup"
    dialog = StorageSetupDialog(data, backup)
    qtbot.addWidget(dialog)
    dialog.backup_input.setText(str(data))
    dialog.accept()
    assert dialog.result() != QDialog.DialogCode.Accepted
    assert "different folder" in dialog.error.text()
    dialog.backup_input.setText(str(data / ".." / "data"))
    dialog.accept()
    assert "different folder" in dialog.error.text()
    dialog.backup_input.setText("relative/backup")
    dialog.accept()
    assert "absolute paths" in dialog.error.text()
    dialog.backup_input.setText(str(backup))
    dialog.accept()
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.selected_settings().data_directory == data
    assert dialog.selected_settings().backup_directory == backup
