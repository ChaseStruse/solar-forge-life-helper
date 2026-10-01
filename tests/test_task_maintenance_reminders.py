"""Task and maintenance reminders are opt-in, private, and claimed per occurrence."""

from datetime import date, datetime, time, timezone

import pytest

from solar_forge_desktop.maintenance import MaintenanceService
from solar_forge_desktop.maintenance_reminders import MaintenanceReminderService
from solar_forge_desktop.storage import Storage
from solar_forge_desktop.task_reminders import TaskReminderService
from solar_forge_desktop.tasks import TaskService


def test_task_reminder_follows_due_date_and_visibility(tmp_path):
    storage = Storage(tmp_path / "family.db")
    owner = storage.default_profile_id()
    member = storage.create_profile("Member")
    tasks = TaskService(storage)
    reminders = TaskReminderService(storage)
    task_id = tasks.add_task(owner, "Pay bill", "household", datetime(2026, 10, 1, 18))
    now = datetime(2026, 10, 1, 22, 35, tzinfo=timezone.utc)
    assert reminders.due(member, now) == ()
    reminders.set_rule(member, task_id, 30, "America/Chicago")
    assert reminders.get_rule(owner, task_id) is None
    due = reminders.due(member, now)
    assert len(due) == 1
    assert due[0].due_at.astimezone(timezone.utc) == datetime(
        2026, 10, 1, 22, 30, tzinfo=timezone.utc,
    )
    assert reminders.mark_delivered(member, due[0], now)
    assert not reminders.mark_delivered(member, due[0], now)
    assert reminders.recent_deliveries(member)[0].title == "Pay bill"
    tasks.set_due_at(owner, task_id, datetime(2026, 10, 2, 18))
    assert len(reminders.due(member, datetime(2026, 10, 2, 22, 35,
                                             tzinfo=timezone.utc))) == 1
    tasks.set_visibility(owner, task_id, "private")
    assert reminders.get_rule(member, task_id) is None
    assert reminders.recent_deliveries(member) == ()
    with pytest.raises(ValueError, match="not found"):
        reminders.set_rule(member, task_id, 0, "UTC")
    storage.close()


def test_task_reminder_skips_completed_and_missing_due_date(tmp_path):
    storage = Storage(tmp_path / "family.db")
    owner = storage.default_profile_id()
    tasks = TaskService(storage)
    reminders = TaskReminderService(storage)
    task_id = tasks.add_task(owner, "No deadline")
    with pytest.raises(ValueError, match="due date"):
        reminders.set_rule(owner, task_id, 0, "UTC")
    tasks.set_due_at(owner, task_id, datetime(2026, 10, 1, 12))
    reminders.set_rule(owner, task_id, 0, "UTC")
    tasks.toggle_task(owner, task_id)
    assert reminders.due(owner, datetime(2026, 10, 1, 12, 1,
                                         tzinfo=timezone.utc)) == ()
    storage.close()


def test_maintenance_reminder_recurs_and_stays_private(tmp_path):
    storage = Storage(tmp_path / "family.db")
    owner = storage.default_profile_id()
    member = storage.create_profile("Member")
    maintenance = MaintenanceService(storage)
    reminders = MaintenanceReminderService(storage)
    item_id = maintenance.add(owner, "Filter", "General", date(2026, 10, 1),
                              1, "months")
    now = datetime(2026, 9, 30, 14, 5, tzinfo=timezone.utc)
    assert reminders.due(owner, now) == ()
    with pytest.raises(ValueError, match="not found"):
        reminders.set_rule(member, item_id, 1, time(9), "America/Chicago")
    reminders.set_rule(owner, item_id, 1, time(9), "America/Chicago")
    assert reminders.get_rule(owner, item_id).time_of_day == time(9)
    due = reminders.due(owner, now)
    assert len(due) == 1
    assert reminders.due(member, now) == ()
    assert reminders.mark_delivered(owner, due[0], now)
    assert reminders.due(owner, now) == ()
    maintenance.complete(owner, item_id, date(2026, 10, 1))
    next_now = datetime(2026, 10, 31, 14, 5, tzinfo=timezone.utc)
    assert len(reminders.due(owner, next_now)) == 1
    assert len(reminders.recent_deliveries(owner)) == 1
    assert reminders.recent_deliveries(member) == ()
    storage.close()
