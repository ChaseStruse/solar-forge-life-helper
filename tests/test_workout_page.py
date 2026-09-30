"""Native workout page navigation, entry, edit, delete, and calendar use."""

from datetime import date
from decimal import Decimal
from pathlib import Path

from PySide6.QtCore import QDate, Qt, QTimer
from PySide6.QtWidgets import QBoxLayout, QDialog, QPushButton

from solar_forge_desktop.storage import Storage
from solar_forge_desktop.tasks import TaskService
from solar_forge_desktop.window import TaskWindow
from solar_forge_desktop.workout import WorkoutService


def test_workout_card_add_edit_delete_and_restart(qtbot, tmp_path: Path) -> None:
    path = tmp_path / "solar-forge.db"
    storage = Storage(path)
    profile = storage.default_profile_id()
    window = TaskWindow(TaskService(storage), profile, storage.close)
    qtbot.addWidget(window)
    window.show()
    card = next(item for item in window.app_cards
                if item.accessibleName() == "Open Workout Tracker")
    qtbot.mouseClick(card, Qt.MouseButton.LeftButton)
    page = window.workout_page
    assert window.pages.currentIndex() == 8
    assert window.workout_nav.isChecked()
    assert page.date_input.calendarWidget().objectName() == "solarForgeCalendar"
    page.date_input.setDate(QDate(2026, 9, 28))
    qtbot.waitUntil(lambda: page.day_description.text().startswith("September 28"))
    assert not page.table_card.isVisible()
    window.resize(800, 600)
    qtbot.waitUntil(lambda: page.columns.direction() == QBoxLayout.Direction.TopToBottom)
    window.resize(1280, 800)
    page.name_input.setText("Bench Press")
    page.sets_input.setText("3")
    page.reps_input.setText("8")
    page.weight_input.setText("135.125")
    page.notes_input.setPlainText("Good form")
    qtbot.mouseClick(page.add_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: page.list_heading.text() == "Today's Exercises (1)")
    assert page.table_card.isVisible()
    assert page.table.item(0, 3).text() == "135.125 lbs"
    assert (page.sets_value.text(), page.reps_value.text()) == ("3", "8")
    edit_actions = page.table.cellWidget(0, 4)

    qtbot.mouseClick(edit_actions.findChildren(QPushButton)[0], Qt.MouseButton.LeftButton)
    editor = page.table.cellWidget(0, 0)
    assert editor.objectName() == "workoutInlineEditor"
    qtbot.mouseClick(next(button for button in editor.findChildren(QPushButton)
                          if button.text() == "Cancel"), Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: page.table.cellWidget(0, 0) is None)
    qtbot.mouseClick(
        page.table.cellWidget(0, 4).findChildren(QPushButton)[0],
        Qt.MouseButton.LeftButton,
    )
    editor = page.table.cellWidget(0, 0)
    fields = editor.findChildren(type(page.name_input), "workoutInput")
    fields[0].setText("Push-ups")
    fields[1].setText("4")
    fields[2].setText("10")
    editor.findChild(type(page.bodyweight), "workoutCheckbox").setChecked(True)
    qtbot.mouseClick(next(button for button in editor.findChildren(QPushButton)
                          if button.text() == "Save"), Qt.MouseButton.LeftButton)
    assert not page.table.isEnabled()
    qtbot.waitUntil(lambda: page.table.item(0, 0).text().startswith("Push-ups"))
    qtbot.waitUntil(page.table.isEnabled)
    assert page.table.item(0, 3).text() == "Bodyweight"
    assert WorkoutService(storage).view(profile, date(2026, 9, 28)).exercises[0].weight_lbs is None
    delete_actions = page.table.cellWidget(0, 4)
    QTimer.singleShot(0, lambda: page.findChild(QDialog, "workoutDeleteDialog").reject())
    qtbot.mouseClick(delete_actions.findChildren(QPushButton)[1], Qt.MouseButton.LeftButton)
    assert WorkoutService(storage).view(profile, date(2026, 9, 28)).exercise_count == 1
    QTimer.singleShot(0, lambda: page.findChild(QDialog, "workoutDeleteDialog").accept())
    qtbot.mouseClick(delete_actions.findChildren(QPushButton)[1], Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: page.list_heading.text() == "Today's Exercises (0)")
    assert not page.table_card.isVisible()
    window.close()
    reopened = Storage(path)
    assert WorkoutService(reopened).view(profile, date(2026, 9, 28)).exercise_count == 0
    reopened.close()


def test_workout_search_dates_bodyweight_and_validation(qtbot, tmp_path: Path) -> None:
    storage = Storage(tmp_path / "solar-forge.db")
    profile = storage.default_profile_id()
    window = TaskWindow(TaskService(storage), profile, storage.close)
    qtbot.addWidget(window)
    window.show()
    window.app_search.setText("exercise")
    window.app_search.returnPressed.emit()
    page = window.workout_page
    assert window.pages.currentIndex() == 8
    page.date_input.setDate(QDate(2026, 9, 28))
    qtbot.mouseClick(page.previous_button, Qt.MouseButton.LeftButton)
    assert page.date_input.date() == QDate(2026, 9, 27)
    qtbot.mouseClick(page.next_button, Qt.MouseButton.LeftButton)
    assert page.date_input.date() == QDate(2026, 9, 28)
    qtbot.waitUntil(page.add_button.isEnabled)
    page.name_input.setText("Pull ups")
    page.sets_input.setText("3")
    page.reps_input.setText("6")
    page.weight_input.setText("100")
    page.bodyweight.setChecked(True)
    assert not page.weight_group.isVisible()
    assert page.weight_input.text() == ""
    qtbot.mouseClick(page.add_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: page.exercise_value.text() == "1")
    item = WorkoutService(storage).view(profile, date(2026, 9, 28)).exercises[0]
    assert (item.is_bodyweight, item.weight_lbs) == (True, None)
    page.name_input.setText("Squat")
    page.sets_input.setText("1")
    page.reps_input.setText("2")
    page.weight_input.setText("NaN")
    qtbot.mouseClick(page.add_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: "valid number" in page.status.text())
    assert WorkoutService(storage).view(profile, date(2026, 9, 28)).exercise_count == 1
    page.weight_input.setText("0")
    qtbot.mouseClick(page.add_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: page.exercise_value.text() == "2")
    saved = WorkoutService(storage).view(profile, date(2026, 9, 28))
    assert saved.exercises[1].weight_lbs == Decimal(0)
    window.close()
