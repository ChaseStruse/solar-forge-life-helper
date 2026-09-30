"""Qt interactions for the desktop weekly Habit Tracker."""

from datetime import date, timedelta
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QBoxLayout, QDialog, QPushButton, QScrollArea

from solar_forge_desktop.habits import HabitService
from solar_forge_desktop.storage import Storage
from solar_forge_desktop.tasks import TaskService
from solar_forge_desktop.window import TaskWindow


def test_habit_week_navigation_toggle_delete_and_restart(qtbot, tmp_path: Path) -> None:
    path = tmp_path / "solar-forge.db"
    storage = Storage(path)
    profile = storage.default_profile_id()
    window = TaskWindow(TaskService(storage), profile, storage.close)
    qtbot.addWidget(window)
    window.show()
    card = next(item for item in window.app_cards
                if item.accessibleName() == "Open Habit Tracker")
    qtbot.mouseClick(card, Qt.MouseButton.LeftButton)
    page = window.habit_page
    assert window.pages.currentIndex() == 5
    assert window.habit_nav.isChecked()
    qtbot.waitUntil(page.add_button.isEnabled)
    assert page.percent_label.text() == "0%"
    window.resize(690, 600)
    qtbot.waitUntil(lambda: page.header.direction() == QBoxLayout.Direction.TopToBottom)
    grid_scroll = page.findChild(QScrollArea, "habitGridScroll")
    assert grid_scroll.horizontalScrollBar().maximum() > 0
    window.resize(1280, 800)
    page.name_input.setText(" Drink water ")
    qtbot.mouseClick(page.add_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: len(page.check_buttons) == 7)
    habit = HabitService(storage).view(profile, page.selected_week).habits[0]
    assert habit.name == "Drink water"
    window.resize(2048, 1024)
    qtbot.waitUntil(lambda: page.grid_scroll.height() <= 150)
    heading = page.grid.itemAtPosition(0, 1).widget()
    check_cell = page.grid.itemAtPosition(1, 1).widget()
    assert check_cell.geometry().center().y() - heading.geometry().center().y() < 100
    day = page.selected_week + timedelta(days=1)
    qtbot.mouseClick(page.check_buttons[(habit.id, day)], Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: page.count_label.text().startswith("1 yes"))
    assert page.percent_label.text() == "14%"
    assert page.check_buttons[(habit.id, day)].isChecked()
    assert not page.check_buttons[(habit.id, day)].icon().isNull()
    assert page.check_buttons[(habit.id, page.selected_week)].icon().isNull()
    qtbot.mouseClick(page.next_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: page.count_label.text().startswith("0 yes"))
    qtbot.mouseClick(page.previous_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: page.count_label.text().startswith("1 yes"))
    window.close()
    reopened = Storage(path)
    assert HabitService(reopened).view(profile, day).completed_count == 1
    reopened.close()


def test_habit_validation_search_and_delete_confirmation(qtbot, tmp_path: Path) -> None:
    storage = Storage(tmp_path / "solar-forge.db")
    profile = storage.default_profile_id()
    window = TaskWindow(TaskService(storage), profile, storage.close)
    qtbot.addWidget(window)
    window.show()
    window.app_search.setText("habits")
    window.app_search.returnPressed.emit()
    page = window.habit_page
    assert window.pages.currentIndex() == 5
    qtbot.waitUntil(page.add_button.isEnabled)
    qtbot.mouseClick(page.add_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: page.status.text() == "Habit name is required.")
    page.name_input.setText("Read")
    qtbot.mouseClick(page.add_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: len(page.check_buttons) == 7)
    page.name_input.setText("read")
    qtbot.mouseClick(page.add_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: "already being tracked" in page.status.text())
    assert len(HabitService(storage).view(profile, date.today()).habits) == 1
    remove = page.findChild(QPushButton, "habitDelete")
    QTimer.singleShot(0, lambda: page.findChild(QDialog, "habitDeleteDialog").reject())
    qtbot.mouseClick(remove, Qt.MouseButton.LeftButton)
    assert len(HabitService(storage).view(profile, date.today()).habits) == 1
    QTimer.singleShot(0, lambda: page.findChild(QDialog, "habitDeleteDialog").accept())
    qtbot.mouseClick(remove, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: not page.check_buttons)
    assert HabitService(storage).view(profile, date.today()).habits == ()
    window.close()
