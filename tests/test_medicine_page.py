"""Qt interactions for the desktop Medicine Tracker."""

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QDateTime, Qt, QTimer
from PySide6.QtWidgets import QBoxLayout, QDialog, QPushButton

from solar_forge_desktop.medicine import MedicineService
from solar_forge_desktop.storage import Storage
from solar_forge_desktop.tasks import TaskService
from solar_forge_desktop.window import TaskWindow


def test_medicine_navigation_create_delete_and_restart(qtbot, tmp_path: Path) -> None:
    path = tmp_path / "solar-forge.db"
    storage = Storage(path)
    profile = storage.default_profile_id()
    window = TaskWindow(TaskService(storage), profile, storage.close)
    qtbot.addWidget(window)
    window.show()
    card = next(
        item for item in window.findChildren(QPushButton, "appCard")
        if item.accessibleName() == "Open Medicine Tracker"
    )
    qtbot.mouseClick(card, Qt.MouseButton.LeftButton)
    page = window.medicine_page
    assert window.pages.currentIndex() == 4
    assert window.medicine_nav.isChecked()
    assert page.given_input.date().year() == datetime.now().year
    assert page.given_input.date().month() == datetime.now().month
    window.resize(800, 600)
    qtbot.waitUntil(lambda: page.columns.direction() == QBoxLayout.Direction.TopToBottom)
    window.resize(690, 600)
    qtbot.waitUntil(lambda: page.summary.direction() == QBoxLayout.Direction.TopToBottom)
    window.resize(1280, 800)
    qtbot.waitUntil(lambda: page.list_heading.text() == "Scheduled Doses (0)")
    qtbot.waitUntil(page.save_button.isEnabled)
    page.recipient_input.setText(" Max ")
    page.name_input.setText(" Medicine ")
    page.dosage_input.setText(" 10 mg ")
    page.given_input.setDateTime(QDateTime.fromString("2026-09-28T08:00", "yyyy-MM-ddTHH:mm"))
    page.next_input.setDateTime(QDateTime.fromString("2026-09-28T20:00", "yyyy-MM-ddTHH:mm"))
    assert page.given_input.dateTime().toString("yyyy-MM-ddTHH:mm") == "2026-09-28T08:00"
    assert page.next_input.dateTime().toString("yyyy-MM-ddTHH:mm") == "2026-09-28T20:00"
    qtbot.mouseClick(page.save_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: page.list_heading.text() == "Scheduled Doses (1)")
    assert page.status.text() == "Medicine dose saved."
    assert page.total_value.text() == "1"
    assert page.people_value.text() == "1"
    assert "Sep 28, 2026" in page.next_value.text()
    entry = MedicineService(storage).view(profile).logs[0]
    assert (entry.recipient, entry.medicine_name, entry.dosage) == ("Max", "Medicine", "10 mg")
    assert entry.next_due_at == "2026-09-28T20:00"
    row = page.list_layout.itemAt(0).widget()
    delete = next(
        button for button in row.findChildren(QPushButton)
        if button.accessibleName() == "Delete Medicine for Max"
    )
    QTimer.singleShot(0, lambda: page.findChild(QDialog, "medicineDeleteDialog").reject())
    qtbot.mouseClick(delete, Qt.MouseButton.LeftButton)
    assert MedicineService(storage).view(profile).total_count == 1
    QTimer.singleShot(0, lambda: page.findChild(QDialog, "medicineDeleteDialog").accept())
    qtbot.mouseClick(delete, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: page.list_heading.text() == "Scheduled Doses (0)")
    assert MedicineService(storage).view(profile).logs == ()
    page.recipient_input.setText("Keep")
    page.name_input.setText("Vitamin")
    page.dosage_input.setText("1 tablet")
    qtbot.mouseClick(page.save_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: page.list_heading.text() == "Scheduled Doses (1)")
    window.close()
    reopened = Storage(path)
    assert MedicineService(reopened).view(profile).logs[0].medicine_name == "Vitamin"
    reopened.close()


def test_medicine_validation_and_search(qtbot, tmp_path: Path) -> None:
    storage = Storage(tmp_path / "solar-forge.db")
    profile = storage.default_profile_id()
    window = TaskWindow(TaskService(storage), profile, storage.close)
    qtbot.addWidget(window)
    window.show()
    window.app_search.setText("medicine")
    window.app_search.returnPressed.emit()
    page = window.medicine_page
    assert window.pages.currentIndex() == 4
    qtbot.waitUntil(page.save_button.isEnabled)
    qtbot.mouseClick(page.save_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: page.status.text() == "Who the medicine is for is required.")
    page.recipient_input.setText("Max")
    page.name_input.setText("Medicine")
    page.dosage_input.setText("10 mg")
    page.next_input.setDateTime(page.given_input.dateTime())
    qtbot.mouseClick(page.save_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: "scheduled after" in page.status.text())
    assert MedicineService(storage).view(profile).total_count == 0
    window.close()
