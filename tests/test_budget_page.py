"""Headless interactions for the desktop Easy Budget page."""

from pathlib import Path

from PySide6.QtCore import QDate, QPoint, Qt
from PySide6.QtWidgets import QFileDialog, QPushButton, QScrollArea

from solar_forge_desktop.budget import BudgetService
from solar_forge_desktop.budget_page import BudgetPage
from solar_forge_desktop.storage import Storage
from solar_forge_desktop.tasks import TaskService
from solar_forge_desktop.window import TaskWindow


def test_budget_navigation_and_persistent_entry(qtbot, tmp_path: Path) -> None:
    storage = Storage(tmp_path / "solar-forge.db")
    profile = storage.default_profile_id()
    window = TaskWindow(TaskService(storage), profile, storage.close)
    qtbot.addWidget(window)
    window.show()
    card = next(
        card for card in window.findChildren(QPushButton, "appCard")
        if card.accessibleName() == "Open Easy Budget"
    )
    qtbot.mouseClick(card, Qt.MouseButton.LeftButton)
    page = window.budget_page
    qtbot.waitUntil(lambda: page.income_button.isEnabled())
    assert window.pages.currentIndex() == 2
    assert window.budget_nav.isChecked()
    assert window.theme_button.menu().actions()[0].text() == "Solar Forge Glow"
    window.theme_button.menu().actions()[2].trigger()
    assert "#06172c" in window.styleSheet()
    calendar = page.month_picker.calendarWidget()
    assert calendar.headerTextFormat().background().color().name() == "#133e68"
    assert "#133e68" in page.styleSheet()
    window.theme_button.menu().actions()[0].trigger()
    assert calendar.headerTextFormat().background().color().name() == "#211b30"
    assert page.income_value.text() == "$0.00"
    assert page.empty.isVisible()
    assert page.income_value.mapToGlobal(page.income_value.rect().topLeft()).x() < (
        page.savings_value.mapToGlobal(page.savings_value.rect().topLeft()).x()
    )
    window.resize(800, 600)
    qtbot.waitUntil(lambda: (
        page.kpis.direction().name == "TopToBottom"
        and page.income_value.mapToGlobal(page.income_value.rect().topLeft()).y()
        < page.expenses_value.mapToGlobal(page.expenses_value.rect().topLeft()).y()
    ))
    window.resize(1280, 800)

    page.income_input.setText("4500.50")
    qtbot.mouseClick(page.income_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: bool(page.status.text()))
    assert page.status.text() == "Income updated successfully!"
    qtbot.waitUntil(lambda: page.income_value.text() == "$4,500.50")
    page.name_input.setText("Rent")
    page.amount_input.setText("1200.25")
    page.tag_input.setText("House")
    qtbot.mouseClick(page.expense_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: page.table_heading.text() == "Logged Expenses (1)")
    assert page.expenses_value.text() == "$1,200.25"
    assert page.savings_value.text() == "$3,300.25"
    assert page.table.item(0, 0).text() == "Rent"
    assert not page.empty.isVisible()

    qtbot.mouseClick(window.dashboard_nav, Qt.MouseButton.LeftButton)
    window.app_search.setText("Easy Budget")
    window.app_search.returnPressed.emit()
    qtbot.waitUntil(lambda: page.table_heading.text() == "Logged Expenses (1)")
    assert window.pages.currentIndex() == 2
    window.close()
    reopened = Storage(tmp_path / "solar-forge.db")
    view = BudgetService(reopened).view(profile, page.month)
    assert (view.income_cents, view.total_expenses_cents) == (450050, 120025)
    reopened.close()


def test_budget_month_recurrence_filter_edit_delete_and_export(
    qtbot, monkeypatch, tmp_path: Path,
) -> None:
    storage = Storage(tmp_path / "solar-forge.db")
    profile = storage.default_profile_id()
    page = BudgetPage(BudgetService(storage), profile)
    qtbot.addWidget(page)
    page.resize(1000, 800)
    page.show()
    page.month_picker.setDate(QDate(2026, 9, 1))
    qtbot.waitUntil(lambda: page.income_description.text().endswith("September 2026"))
    page.name_input.setText("Internet")
    page.amount_input.setText("45.00")
    page.tag_input.setText("Subscriptions")
    page.due_input.setDate(QDate(2026, 9, 7))
    assert page.recurrence_input.isVisible()
    page.recurrence_input.setCurrentIndex(page.recurrence_input.findData("weekly"))
    qtbot.mouseClick(page.expense_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: page.table_heading.text() == "Logged Expenses (4)")
    assert page.expenses_value.text() == "$180.00"
    assert not page.recurrence_input.isVisible()

    page.tag_filter.setCurrentIndex(page.tag_filter.findData("House"))
    qtbot.waitUntil(lambda: page.table_heading.text() == "Logged Expenses (0)")
    assert page.expenses_value.text() == "$180.00"
    page.tag_filter.setCurrentIndex(0)
    qtbot.waitUntil(lambda: page.table_heading.text() == "Logged Expenses (4)")

    export_path = tmp_path / "budget.csv"
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", lambda *_args: (str(export_path), "CSV files (*.csv)")
    )
    qtbot.mouseClick(page.export_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(export_path.exists)
    assert export_path.read_text().count("Internet") == 4

    edit = page.table.cellWidget(0, 4).findChild(QPushButton, "budgetEdit")
    qtbot.mouseClick(edit, Qt.MouseButton.LeftButton)
    name_field = page.table.cellWidget(0, 0)
    name_field.setText("Fiber")
    save = page.table.cellWidget(0, 4).findChild(QPushButton, "budgetPrimary")
    qtbot.mouseClick(save, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: any(
        page.table.item(row, 0).text() == "Fiber" for row in range(page.table.rowCount())
    ))
    assert page.expenses_value.text() == "$180.00"

    page.month_picker.setDate(QDate(2026, 10, 1))
    qtbot.waitUntil(lambda: page.table_heading.text() == "Logged Expenses (4)")
    assert page.expenses_value.text() == "$180.00"
    page.shutdown()
    storage.close()


def test_optional_due_calendar_opens_on_current_month_without_setting_date(
    qtbot, tmp_path: Path,
) -> None:
    storage = Storage(tmp_path / "solar-forge.db")
    page = BudgetPage(BudgetService(storage), storage.default_profile_id())
    qtbot.addWidget(page)
    page.show()
    today = QDate.currentDate()
    assert page.month_picker.date().year() == today.year()
    assert page.month_picker.date().month() == today.month()
    assert page.due_input.date() == page.due_input.minimumDate()
    assert page._due_text(page.due_input) == ""

    calendar = page.due_input.calendarWidget()
    page.findChild(QScrollArea, "budgetScroll").ensureWidgetVisible(page.due_input)
    qtbot.mouseClick(
        page.due_input, Qt.MouseButton.LeftButton,
        pos=QPoint(page.due_input.width() - 8, page.due_input.height() // 2),
    )
    qtbot.waitUntil(calendar.isVisible)
    qtbot.waitUntil(
        lambda: (calendar.yearShown(), calendar.monthShown()) ==
        (today.year(), today.month())
    )
    assert page._due_text(page.due_input) == ""
    assert "#151027" in calendar.styleSheet() or "#151027" in page.styleSheet()

    selected = QDate(today.year(), today.month(), 15)
    calendar.clicked.emit(selected)
    assert page._due_text(page.due_input) == selected.toString("yyyy-MM-dd")
    page.shutdown()
    storage.close()
