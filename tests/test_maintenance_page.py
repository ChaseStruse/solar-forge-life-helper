"""Qt interactions for Home Maintenance."""

from datetime import date
from pathlib import Path

from PySide6.QtCore import QDate, Qt, QTimer
from PySide6.QtWidgets import QBoxLayout, QDialog, QPushButton

from solar_forge_desktop.maintenance import MaintenanceService
from solar_forge_desktop.storage import Storage
from solar_forge_desktop.tasks import TaskService
from solar_forge_desktop.window import TaskWindow


def test_maintenance_card_create_complete_delete_restart(qtbot, tmp_path: Path) -> None:
    path = tmp_path / "solar-forge.db"
    storage = Storage(path)
    profile = storage.default_profile_id()
    window = TaskWindow(TaskService(storage), profile, storage.close)
    qtbot.addWidget(window)
    window.show()
    card = next(item for item in window.app_cards
                if item.accessibleName() == "Open Home Maintenance")
    qtbot.mouseClick(card, Qt.MouseButton.LeftButton)
    page = window.maintenance_page
    assert window.pages.currentIndex() == 11
    assert window.maintenance_nav.isChecked()
    qtbot.waitUntil(page.add_button.isEnabled)
    assert page.due_input.calendarWidget().objectName() == "solarForgeCalendar"
    assert page.unit_input.currentData() == "months"
    page.name_input.setText("Replace HVAC filter")
    page.category_input.setCurrentText("Appliances")
    page.due_input.setDate(QDate.currentDate())
    page.interval_input.setText("3")
    page.cost_input.setText("18.50")
    page.notes_input.setPlainText("Size 16x20")
    qtbot.mouseClick(page.add_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: page.tracked_value.text() == "1")
    item = MaintenanceService(storage).view(profile).items[0]
    assert (item.name, item.category, str(item.estimated_cost)) == (
        "Replace HVAC filter", "Appliances", "18.50"
    )
    assert page.soon_value.text() == "1"
    card = page.items_layout.itemAt(0).widget()
    complete = next(button for button in card.findChildren(QPushButton)
                    if button.text() == "Mark Complete")
    qtbot.mouseClick(complete, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: MaintenanceService(storage).view(profile).items[0]
                    .last_completed_date == date.today())
    qtbot.waitUntil(lambda: page.items_container.isEnabled())
    assert page.tracked_value.text() == "1"
    window.resize(800, 600)
    qtbot.waitUntil(lambda: page.columns.direction() == QBoxLayout.Direction.TopToBottom)
    card = page.items_layout.itemAt(0).widget()
    remove = next(button for button in card.findChildren(QPushButton)
                  if button.accessibleName() == "Remove Replace HVAC filter")
    QTimer.singleShot(0, lambda: page.findChild(QDialog, "maintenanceDeleteDialog").reject())
    qtbot.mouseClick(remove, Qt.MouseButton.LeftButton)
    assert MaintenanceService(storage).view(profile).total == 1
    QTimer.singleShot(0, lambda: page.findChild(QDialog, "maintenanceDeleteDialog").accept())
    qtbot.mouseClick(remove, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: page.tracked_value.text() == "0")
    window.close()
    reopened = Storage(path)
    assert MaintenanceService(reopened).view(profile).total == 0
    reopened.close()


def test_maintenance_search_validation_and_calendar(qtbot, tmp_path: Path) -> None:
    storage = Storage(tmp_path / "solar-forge.db")
    profile = storage.default_profile_id()
    window = TaskWindow(TaskService(storage), profile, storage.close)
    qtbot.addWidget(window)
    window.show()
    window.app_search.setText("maintenance")
    window.app_search.returnPressed.emit()
    page = window.maintenance_page
    assert window.pages.currentIndex() == 11
    qtbot.waitUntil(page.add_button.isEnabled)
    qtbot.mouseClick(page.add_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: "name is required" in page.status.text())
    page.name_input.setText("Inspect roof")
    page.interval_input.setText("0")
    qtbot.mouseClick(page.add_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: "repeat interval" in page.status.text())
    page.interval_input.setText("1")
    page.cost_input.setText("-1")
    qtbot.mouseClick(page.add_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: "zero or greater" in page.status.text())
    assert MaintenanceService(storage).view(profile).total == 0
    window.close()
