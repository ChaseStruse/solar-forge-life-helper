"""Headless Qt interaction coverage for the native Calendar page."""

from datetime import date, datetime, timezone
from pathlib import Path

from PySide6.QtCore import QDate, Qt, QTime
from PySide6.QtWidgets import QLabel, QMessageBox, QPushButton

from solar_forge_desktop.calendar import CalendarService
from solar_forge_desktop.reminders import CalendarReminderService
from solar_forge_desktop.storage import Storage
from solar_forge_desktop.tasks import TaskService
from solar_forge_desktop.window import TaskWindow


def test_calendar_reminder_controls_and_history(qtbot, tmp_path: Path) -> None:
    storage = Storage(tmp_path / "solar-forge.db")
    profile = storage.default_profile_id()
    window = TaskWindow(TaskService(storage), profile, storage.close)
    qtbot.addWidget(window)
    window.show()
    window.show_calendar()
    page = window.calendar_page
    qtbot.waitUntil(lambda: page.save_button.isEnabled() and bool(page.period_label.text()))
    page.title_input.setText("Dentist")
    page.category_input.setText("Health")
    page.start_date_input.setDate(QDate(2026, 10, 1))
    page.start_time_input.setTime(QTime(18, 0))
    page.reminder_enabled.setChecked(True)
    page.reminder_lead.setCurrentIndex(page.reminder_lead.findData(30))
    page.reminder_zone.setCurrentIndex(page.reminder_zone.findText("America/Chicago"))
    page.scroll.ensureWidgetVisible(page.save_button)
    qtbot.mouseClick(page.save_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: bool(page.status.text()))
    assert page.status.text() == "Added Dentist."
    event = next(items[0].event for _, items in CalendarService(storage).view(
        profile, date(2026, 10, 1)
    ).days if items)
    reminders = CalendarReminderService(storage)
    rule = reminders.get_rule(profile, event.id)
    assert (rule.lead_minutes, rule.timezone_id) == (30, "America/Chicago")
    now = datetime(2026, 10, 1, 22, 35, tzinfo=timezone.utc)
    due = reminders.due(profile, now)
    assert len(due) == 1
    assert reminders.mark_delivered(profile, due[0], now)
    page.refresh_reminder_history()
    assert "Dentist" in page.reminder_history.text()
    assert "America/Chicago" in page.reminder_history.text()

    page.edit_event(event.id)
    assert page.reminder_enabled.isChecked()
    assert page.reminder_lead.currentData() == 30
    page.reminder_enabled.setChecked(False)
    qtbot.waitUntil(page.save_button.isEnabled)
    page.scroll.ensureWidgetVisible(page.save_button)
    qtbot.mouseClick(page.save_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: page.status.text() == "Updated Dentist.")
    assert reminders.get_rule(profile, event.id) is None
    assert page.reminder_history.text() == "No reminders delivered yet."
    window.close()


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


def test_calendar_sharing_form_and_member_edit(qtbot, tmp_path: Path) -> None:
    storage = Storage(tmp_path / "solar-forge.db")
    owner = storage.default_profile_id()
    member = storage.create_profile("Member")
    service = CalendarService(storage)
    window = TaskWindow(TaskService(storage), owner, lambda: None)
    qtbot.addWidget(window)
    window.show()
    window.show_calendar()
    page = window.calendar_page
    qtbot.waitUntil(lambda: bool(page.period_label.text()))
    page.title_input.setText("Family outing")
    page.category_input.setText("Family")
    page.start_date_input.setDate(QDate(2026, 9, 28))
    page.visibility_input.setCurrentIndex(page.visibility_input.findData("household"))
    qtbot.mouseClick(page.save_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: page.status.text() == "Added Family outing.")
    event = next(items[0].event for _, items in service.view(owner, date(2026, 9, 28)).days
                 if items)
    assert event.visibility == "household"
    assert page.visibility_input.currentData() == "private"
    window.close()

    member_window = TaskWindow(TaskService(storage), member, lambda: None)
    qtbot.addWidget(member_window)
    member_window.show()
    member_window.show_calendar()
    member_page = member_window.calendar_page
    member_page.selected = date(2026, 9, 28)
    member_page.refresh()
    qtbot.waitUntil(lambda: member_page.count_label.text() == "1 event")
    assert member_page.findChildren(QPushButton, "calendarDanger") == []
    member_page.edit_event(event.id)
    assert member_page.visibility_input.currentData() == "household"
    assert not member_page.visibility_input.isEnabled()
    member_page.title_input.setText("Updated outing")
    qtbot.mouseClick(member_page.save_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: member_page.status.text() == "Updated Updated outing.")
    assert service.get(owner, event.id).title == "Updated outing"
    assert service.get(owner, event.id).visibility == "household"
    member_window.close()
    storage.close()
