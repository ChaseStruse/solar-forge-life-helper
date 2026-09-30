"""Qt interactions for the weekly Meal Planner."""

from datetime import timedelta
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QBoxLayout, QCheckBox, QComboBox, QPushButton

from solar_forge_desktop.meals import MealService
from solar_forge_desktop.storage import Storage
from solar_forge_desktop.tasks import TaskService
from solar_forge_desktop.window import TaskWindow


def test_meal_card_week_plan_favorite_reuse_and_groceries(qtbot, tmp_path: Path) -> None:
    path = tmp_path / "solar-forge.db"
    storage = Storage(path)
    profile = storage.default_profile_id()
    window = TaskWindow(TaskService(storage), profile, storage.close)
    qtbot.addWidget(window)
    window.show()
    card = next(item for item in window.app_cards
                if item.accessibleName() == "Open Meal Planner")
    qtbot.mouseClick(card, Qt.MouseButton.LeftButton)
    page = window.meal_page
    assert window.pages.currentIndex() == 10
    assert window.meal_nav.isChecked()
    qtbot.waitUntil(lambda: page.days_layout.count() == 1)
    assert page.days_widget.layout().count() == 7
    start = page.week_start
    qtbot.mouseClick(page.previous_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: page.week_start == start - timedelta(days=7))
    qtbot.waitUntil(page.next_button.isEnabled)
    qtbot.mouseClick(page.next_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: page.week_start == start)
    qtbot.waitUntil(lambda: page.days_widget.isEnabled())
    monday = page.days_widget.layout().itemAt(0).widget()
    name = next(field for field in monday.findChildren(type(page.favorite_name))
                if field.accessibleName() == "Meal for Monday")
    name.setText("Tacos")
    monday.findChild(QCheckBox, "mealCheck").setChecked(True)
    qtbot.mouseClick(next(button for button in monday.findChildren(QPushButton)
                          if button.text() == "Add"), Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: page.favorites_count.text() == "1")
    assert MealService(storage).view(profile, start).days[0][1].name == "Tacos"
    qtbot.mouseClick(page.new_favorite_button, Qt.MouseButton.LeftButton)
    page.favorite_name.setText("Soup")
    page.favorite_ingredients.setPlainText("Rice\nCarrots")
    qtbot.mouseClick(page.save_favorite_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: page.favorites_count.text() == "2")
    soup_row = next(
        row for row in page.favorites_card.findChildren(type(page.days_widget))
        if any(label.text() == "Soup" for label in row.findChildren(type(page.week_label)))
    )
    qtbot.mouseClick(next(button for button in soup_row.findChildren(QPushButton)
                          if button.text() == "Use"), Qt.MouseButton.LeftButton)
    day_select = soup_row.findChild(QComboBox, "mealDay")
    day_select.setCurrentIndex(1)
    qtbot.mouseClick(next(button for button in soup_row.findChildren(QPushButton)
                          if button.text() == "Add"), Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: page.grocery_count.text() == "2 items")
    assert MealService(storage).view(profile, start).days[1][1].name == "Soup"
    assert page.grocery_layout.count() == 2
    window.resize(800, 600)
    qtbot.waitUntil(lambda: page.columns.direction() == QBoxLayout.Direction.TopToBottom)
    window.close()
    reopened = Storage(path)
    assert MealService(reopened).view(profile, start).days[1][1].name == "Soup"
    reopened.close()


def test_meal_search_validation_and_clear(qtbot, tmp_path: Path) -> None:
    storage = Storage(tmp_path / "solar-forge.db")
    profile = storage.default_profile_id()
    window = TaskWindow(TaskService(storage), profile, storage.close)
    qtbot.addWidget(window)
    window.show()
    window.app_search.setText("dinner")
    window.app_search.returnPressed.emit()
    page = window.meal_page
    assert window.pages.currentIndex() == 10
    qtbot.waitUntil(lambda: page.days_layout.count() == 1)
    qtbot.waitUntil(page.days_widget.isEnabled)
    monday = page.days_widget.layout().itemAt(0).widget()
    qtbot.mouseClick(next(button for button in monday.findChildren(QPushButton)
                          if button.text() == "Add"), Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: "meal name" in page.status.text())
    service = MealService(storage)
    service.save_plan(profile, page.week_start, "Salad")
    page.refresh()
    qtbot.waitUntil(lambda: bool(page.days_widget.layout().itemAt(0).widget()
                    .findChildren(QPushButton, "mealClear")))
    monday = page.days_widget.layout().itemAt(0).widget()
    qtbot.mouseClick(monday.findChild(QPushButton, "mealClear"), Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: service.view(profile, page.week_start).days[0][1] is None)
    window.close()
