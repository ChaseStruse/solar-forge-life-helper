"""Qt interactions for the desktop Easy Calorie Tracker."""

from datetime import date
from pathlib import Path

from PySide6.QtCore import QDate, QPoint, Qt, QTimer
from PySide6.QtWidgets import QBoxLayout, QDialog, QScrollArea

from solar_forge_desktop.calorie import CalorieService
from solar_forge_desktop.storage import Storage
from solar_forge_desktop.tasks import TaskService
from solar_forge_desktop.window import TaskWindow


def test_calorie_date_goal_food_delete_and_restart(qtbot, tmp_path: Path) -> None:
    path = tmp_path / "solar-forge.db"
    storage = Storage(path)
    profile = storage.default_profile_id()
    window = TaskWindow(TaskService(storage), profile, storage.close)
    qtbot.addWidget(window)
    window.show()
    card = next(item for item in window.app_cards
                if item.accessibleName() == "Open Calorie Tracker")
    qtbot.mouseClick(card, Qt.MouseButton.LeftButton)
    page = window.calorie_page
    assert window.pages.currentIndex() == 6
    assert window.calorie_nav.isChecked()
    assert page.date_input.calendarWidget().objectName() == "solarForgeCalendar"
    window.resize(800, 600)
    qtbot.waitUntil(lambda: page.columns.direction() == QBoxLayout.Direction.TopToBottom)
    window.resize(1280, 800)
    page.date_input.setDate(QDate(2026, 7, 14))
    qtbot.waitUntil(lambda: "July 14, 2026" in page.consumed_description.text())
    qtbot.waitUntil(page.save_goal_button.isEnabled)
    qtbot.mouseClick(page.edit_goal_button, Qt.MouseButton.LeftButton)
    assert page.goal_editor.isVisible()
    page.goal_input.setText("2250")
    qtbot.mouseClick(page.save_goal_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: page.status.text() != "")
    assert page.status.text() == "Daily calorie target updated successfully!"
    qtbot.waitUntil(lambda: page.target_value.text() == "2,250 kcal")
    assert page.goal_description.text() == "Set specifically for this date"
    page.food_input.setText(" Oatmeal ")
    page.calories_input.setText("320")
    qtbot.mouseClick(page.add_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: page.list_heading.text() == "Logged Foods (1)")
    assert page.table_card.isVisible()
    assert page.table.parentWidget() is page.table_card
    assert page.table_card.layout().contentsMargins().left() == 8
    assert page.consumed_value.text() == "320 kcal"
    assert page.remaining_value.text() == "1,930 kcal"
    assert page.progress_label.text() == "14% Consumed"
    assert page.table.item(0, 0).text() == "Oatmeal"
    food = CalorieService(storage).view(profile, date(2026, 7, 14)).foods[0]
    delete = page.table.cellWidget(0, 2)
    QTimer.singleShot(0, lambda: page.findChild(QDialog, "calorieDeleteDialog").reject())
    qtbot.mouseClick(delete, Qt.MouseButton.LeftButton)
    assert CalorieService(storage).view(profile, date(2026, 7, 14)).total_logs == 1
    QTimer.singleShot(0, lambda: page.findChild(QDialog, "calorieDeleteDialog").accept())
    qtbot.mouseClick(delete, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: page.list_heading.text() == "Logged Foods (0)")
    assert not page.table_card.isVisible()
    assert CalorieService(storage).view(profile, date(2026, 7, 14)).foods == ()
    assert food.food_name == "Oatmeal"
    page.date_input.setDate(QDate(2026, 7, 15))
    qtbot.waitUntil(lambda: page.goal_description.text() == "Inherited from past setting")
    assert page.target_value.text() == "2,250 kcal"
    window.close()
    reopened = Storage(path)
    assert CalorieService(reopened).view(profile, date(2026, 7, 14)).target == 2250
    reopened.close()


def test_calorie_validation_and_search(qtbot, tmp_path: Path) -> None:
    storage = Storage(tmp_path / "solar-forge.db")
    profile = storage.default_profile_id()
    window = TaskWindow(TaskService(storage), profile, storage.close)
    qtbot.addWidget(window)
    window.show()
    window.app_search.setText("calories")
    window.app_search.returnPressed.emit()
    page = window.calorie_page
    assert window.pages.currentIndex() == 6
    qtbot.waitUntil(page.add_button.isEnabled)
    qtbot.mouseClick(page.add_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: page.status.text() == "Food name is required.")
    page.food_input.setText("Apple")
    page.calories_input.setText("-5")
    qtbot.mouseClick(page.add_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: page.status.text() == "Calories cannot be negative.")
    qtbot.mouseClick(page.edit_goal_button, Qt.MouseButton.LeftButton)
    page.goal_input.setText("0")
    qtbot.mouseClick(page.save_goal_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: page.status.text() == "Calorie target must be greater than zero.")
    assert CalorieService(storage).view(profile, date.today()).total_logs == 0
    window.close()


def test_calorie_date_uses_shared_calendar_popup(qtbot, tmp_path: Path) -> None:
    storage = Storage(tmp_path / "solar-forge.db")
    window = TaskWindow(TaskService(storage), storage.default_profile_id(), storage.close)
    qtbot.addWidget(window)
    window.show()
    window.show_calorie()
    page = window.calorie_page
    page.date_input.setDate(QDate(2026, 7, 14))
    qtbot.waitUntil(lambda: "July 14, 2026" in page.consumed_description.text())
    page.findChild(QScrollArea, "calorieScroll").ensureWidgetVisible(page.date_input)
    calendar = page.date_input.calendarWidget()
    qtbot.mouseClick(
        page.date_input, Qt.MouseButton.LeftButton,
        pos=QPoint(page.date_input.width() - 8, page.date_input.height() // 2),
    )
    qtbot.waitUntil(calendar.isVisible)
    assert (calendar.yearShown(), calendar.monthShown()) == (2026, 7)
    assert "#151027" in page.styleSheet()
    calendar.clicked.emit(QDate(2026, 7, 15))
    qtbot.waitUntil(lambda: "July 15, 2026" in page.consumed_description.text())
    window.close()
