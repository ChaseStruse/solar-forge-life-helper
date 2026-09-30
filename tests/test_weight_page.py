"""Qt interactions for the desktop Weight Progression Tracker."""

from datetime import date
from decimal import Decimal
from pathlib import Path

from PySide6.QtCore import QDate, QPoint, Qt, QTimer
from PySide6.QtWidgets import QBoxLayout, QDialog, QScrollArea

from solar_forge_desktop.storage import Storage
from solar_forge_desktop.tasks import TaskService
from solar_forge_desktop.weight import WeightService
from solar_forge_desktop.window import TaskWindow


def test_weight_goal_weigh_ins_chart_delete_and_restart(qtbot, tmp_path: Path) -> None:
    path = tmp_path / "solar-forge.db"
    storage = Storage(path)
    profile = storage.default_profile_id()
    window = TaskWindow(TaskService(storage), profile, storage.close)
    qtbot.addWidget(window)
    window.show()
    card = next(item for item in window.app_cards
                if item.accessibleName() == "Open Weight Tracker")
    qtbot.mouseClick(card, Qt.MouseButton.LeftButton)
    page = window.weight_page
    assert window.pages.currentIndex() == 7
    assert window.weight_nav.isChecked()
    qtbot.waitUntil(page.save_goal_button.isEnabled)
    assert page.goal_card.isVisible()
    assert not page.chart_card.isVisible()
    window.resize(800, 600)
    qtbot.waitUntil(lambda: page.columns.direction() == QBoxLayout.Direction.TopToBottom)
    window.resize(1280, 800)
    assert page.start_date.calendarWidget().objectName() == "solarForgeCalendar"
    assert page.weigh_date.calendarWidget().objectName() == "solarForgeCalendar"
    page.start_input.setText("200.0")
    page.start_date.setDate(QDate(2026, 7, 1))
    page.goal_input.setText("180.0")
    page.goal_date.setDate(QDate(2026, 8, 1))
    qtbot.mouseClick(page.save_goal_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: page.target_value.text() == "180.0")
    assert page.chart_card.isVisible()
    assert not page.goal_card.isVisible()
    page.weight_input.setText("198.125")
    page.weigh_date.setDate(QDate(2026, 7, 10))
    qtbot.mouseClick(page.log_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: page.history_heading.text() == "Weigh-In Logs (1)")
    assert page.table_card.isVisible()
    assert page.current_value.text() == "198.1"
    assert page.stat_cards[0][1].objectName() == "weightGreen"
    assert page.chart.points[-1] == (date(2026, 7, 10), Decimal("198.125"))
    page.weight_input.setText("196.5")
    qtbot.mouseClick(page.log_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: page.current_value.text() == "196.5")
    assert page.history_heading.text() == "Weigh-In Logs (1)"
    assert WeightService(storage).view(profile).logs[0].weight == Decimal("196.5")
    qtbot.mouseClick(page.edit_target_button, Qt.MouseButton.LeftButton)
    page.target_input.setText("185")
    qtbot.mouseClick(page.save_target_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: page.target_value.text() == "185.0")
    assert page.stat_cards[2][1].text() == "23%"
    delete = page.table.cellWidget(0, 3)
    QTimer.singleShot(0, lambda: page.findChild(QDialog, "weightDeleteDialog").reject())
    qtbot.mouseClick(delete, Qt.MouseButton.LeftButton)
    assert WeightService(storage).view(profile).total_logs == 1
    QTimer.singleShot(0, lambda: page.findChild(QDialog, "weightDeleteDialog").accept())
    qtbot.mouseClick(delete, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: page.history_heading.text() == "Weigh-In Logs (0)")
    assert not page.table_card.isVisible()
    window.close()
    reopened = Storage(path)
    assert WeightService(reopened).view(profile).goal.target_weight == Decimal("185")
    assert WeightService(reopened).view(profile).total_logs == 0
    reopened.close()


def test_weight_validation_search_and_gain_goal(qtbot, tmp_path: Path) -> None:
    storage = Storage(tmp_path / "solar-forge.db")
    profile = storage.default_profile_id()
    window = TaskWindow(TaskService(storage), profile, storage.close)
    qtbot.addWidget(window)
    window.show()
    window.app_search.setText("weight")
    window.app_search.returnPressed.emit()
    page = window.weight_page
    assert window.pages.currentIndex() == 7
    qtbot.waitUntil(page.save_goal_button.isEnabled)
    qtbot.mouseClick(page.log_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: "valid weight" in page.status.text())
    page.start_input.setText("150")
    page.goal_input.setText("160")
    page.start_date.setDate(QDate(2026, 7, 1))
    page.goal_date.setDate(QDate(2026, 7, 31))
    qtbot.mouseClick(page.save_goal_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: page.target_value.text() == "160.0")
    page.weight_input.setText("155")
    page.weigh_date.setDate(QDate(2026, 7, 14))
    qtbot.mouseClick(page.log_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: page.stat_cards[2][1].text() == "50%")
    assert not WeightService(storage).view(profile).is_losing
    window.close()


def test_weight_date_uses_shared_calendar_popup(qtbot, tmp_path: Path) -> None:
    storage = Storage(tmp_path / "solar-forge.db")
    window = TaskWindow(TaskService(storage), storage.default_profile_id(), storage.close)
    qtbot.addWidget(window)
    window.show()
    window.show_weight()
    page = window.weight_page
    qtbot.waitUntil(page.save_goal_button.isEnabled)
    page.start_date.setDate(QDate(2026, 7, 14))
    page.findChild(QScrollArea, "weightScroll").ensureWidgetVisible(page.start_date)
    calendar = page.start_date.calendarWidget()
    qtbot.mouseClick(
        page.start_date, Qt.MouseButton.LeftButton,
        pos=QPoint(page.start_date.width() - 8, page.start_date.height() // 2),
    )
    qtbot.waitUntil(calendar.isVisible)
    assert (calendar.yearShown(), calendar.monthShown()) == (2026, 7)
    assert calendar.objectName() == "solarForgeCalendar"
    calendar.clicked.emit(QDate(2026, 7, 15))
    assert page.start_date.date() == QDate(2026, 7, 15)
    window.close()
