"""Headless Qt interaction coverage for the native Calendar page."""

from datetime import date
from pathlib import Path

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import QLabel, QMessageBox

from solar_forge_desktop.calendar import CalendarService
from solar_forge_desktop.storage import Storage
from solar_forge_desktop.tasks import TaskService
from solar_forge_desktop.window import TaskWindow


def test_calendar_form_views_series_edit_delete_and_restart(qtbot, monkeypatch,
                                                              tmp_path: Path) -> None:
    path = tmp_path / "solar-forge.db"
    storage = Storage(path)
    profile = storage.default_profile_id()
    window = TaskWindow(TaskService(storage), profile, storage.close)
    qtbot.addWidget(window)
    window.resize(1280, 800)
    window.show()
    qtbot.mouseClick(window.calendar_nav, Qt.MouseButton.LeftButton)
    page = window.calendar_page
    qtbot.waitUntil(lambda: bool(page.period_label.text()))
    assert window.pages.currentIndex() == 12
    assert page.findChild(QLabel, "calendarTitle").text() == "Calendar"
    page.title_input.setText("Dentist")
    page.category_input.setText("Health")
    page.description_input.setPlainText("Bring card")
    page.start_date_input.setDate(QDate(2026, 9, 28))
    page.recurrence_input.setCurrentIndex(page.recurrence_input.findData("weekly"))
    page.until_enabled.setChecked(True)
    page.until_input.setDate(QDate(2026, 10, 12))
    qtbot.mouseClick(page.save_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: page.count_label.text() == "1 event")
    assert page.status.text() == "Added Dentist."
    service = CalendarService(storage)
    event = service.view(profile, date(2026, 9, 28)).days[28][1][0].event
    page.edit_event(event.id)
    assert page.form_hint.text() == "Changes apply to the full recurring series."
    page.title_input.setText("Checkup")
    qtbot.mouseClick(page.save_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: page.status.text() == "Updated Checkup.")
    assert service.get(profile, event.id).title == "Checkup"
    qtbot.mouseClick(page.week_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: page.period_label.text() == "Sep 28 - Oct 4, 2026")
    assert page.period_label.text() == "Sep 28 - Oct 4, 2026"
    page.navigate(1)
    qtbot.waitUntil(lambda: page.period_label.text() == "Oct 5 - 11, 2026")
    assert page.count_label.text() == "1 event"
    window.close()

    reopened = Storage(path)
    assert CalendarService(reopened).get(profile, event.id).title == "Checkup"
    reopened.close()


def test_calendar_all_day_validation_and_delete(qtbot, monkeypatch, tmp_path: Path) -> None:
    storage = Storage(tmp_path / "solar-forge.db")
    profile = storage.default_profile_id()
    window = TaskWindow(TaskService(storage), profile, storage.close)
    qtbot.addWidget(window)
    window.show()
    window.show_calendar()
    page = window.calendar_page
    qtbot.waitUntil(lambda: bool(page.period_label.text()))
    page.title_input.setText("Trip")
    page.category_input.setText("Travel")
    page.all_day_input.setChecked(True)
    assert not page.start_time_input.isVisible()
    page.start_date_input.setDate(QDate(2026, 9, 28))
    page.end_date_enabled.setChecked(True)
    page.end_date_input.setDate(QDate(2026, 9, 30))
    qtbot.mouseClick(page.save_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: page.status.text() == "Added Trip.")
    service = CalendarService(storage)
    event = next(items[0].event for _, items in service.view(profile, date(2026, 9, 28)).days
                 if items)
    assert event.all_day
    assert event.ends_at.date() == date(2026, 10, 1)
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    page.delete_event(event)
    qtbot.waitUntil(lambda: page.status.text() == "Removed Trip.")
    assert service.view(profile, date(2026, 9, 28)).event_count == 0
    window.close()
