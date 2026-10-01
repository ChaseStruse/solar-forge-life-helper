"""Due calendar reminders are claimed once and surfaced to the signed-in window."""

from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import QObject

from solar_forge_desktop.calendar import CalendarService
from solar_forge_desktop.medicine import MedicineService
from solar_forge_desktop.medicine_reminders import MedicineReminderService
from solar_forge_desktop.reminder_scheduler import ReminderScheduler
from solar_forge_desktop.reminders import CalendarReminderService
from solar_forge_desktop.storage import Storage


def test_scheduler_claims_due_reminder_once(qtbot, tmp_path: Path) -> None:
    storage = Storage(tmp_path / "solar-forge.db")
    profile = storage.default_profile_id()
    event_id = CalendarService(storage).save(
        profile, "Dentist", None, "Health", datetime(2026, 10, 1, 18),
        datetime(2026, 10, 1, 19),
    )
    service = CalendarReminderService(storage)
    service.set_rule(profile, event_id, 30, "America/Chicago")
    parent = QObject()
    scheduler = ReminderScheduler(
        service, profile, parent,
        clock=lambda: datetime(2026, 10, 1, 22, 35, tzinfo=timezone.utc),
    )
    received = []
    scheduler.delivered.connect(received.append)
    scheduler.start()
    qtbot.waitUntil(lambda: len(received) == 1)
    assert received[0][0].title == "Dentist"
    assert len(service.recent_deliveries(profile)) == 1

    scheduler.check()
    qtbot.waitUntil(lambda: not scheduler._busy)
    assert len(received) == 1
    scheduler.shutdown()
    storage.close()


def test_scheduler_claims_medicine_reminder(qtbot, tmp_path: Path) -> None:
    storage = Storage(tmp_path / "solar-forge.db")
    profile = storage.default_profile_id()
    log_id = MedicineService(storage).add_log(
        profile, "Max", "Antibiotic", "10 mg", "2026-10-01T08:00", "2026-10-01T18:00"
    )
    medicine = MedicineReminderService(storage)
    medicine.set_rule(profile, log_id, 30, "America/Chicago")
    parent = QObject()
    scheduler = ReminderScheduler(
        CalendarReminderService(storage), profile, parent,
        clock=lambda: datetime(2026, 10, 1, 22, 35, tzinfo=timezone.utc),
        medicine=medicine,
    )
    received = []
    scheduler.delivered.connect(received.append)
    scheduler.start()
    qtbot.waitUntil(lambda: len(received) == 1)
    assert received[0][0].title == "Antibiotic for Max"
    assert len(medicine.recent_deliveries(profile)) == 1
    scheduler.shutdown()
    storage.close()
