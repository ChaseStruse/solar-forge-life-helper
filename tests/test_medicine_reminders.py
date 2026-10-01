"""Next-dose reminders respect account boundaries and survive restart."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from solar_forge_desktop.medicine import MedicineService
from solar_forge_desktop.medicine_reminders import MedicineReminderService
from solar_forge_desktop.storage import Storage


def test_medicine_reminder_delivery_and_privacy(tmp_path: Path) -> None:
    path = tmp_path / "family.db"
    storage = Storage(path)
    owner = storage.default_profile_id()
    other = storage.create_profile("Other")
    log_id = MedicineService(storage).add_log(
        owner, "Max", "Antibiotic", "10 mg", "2026-10-01T08:00", "2026-10-01T18:00"
    )
    service = MedicineReminderService(storage)
    with pytest.raises(ValueError, match="not found"):
        service.set_rule(other, log_id, 30, "America/Chicago")
    service.set_rule(owner, log_id, 30, "America/Chicago")
    assert service.get_rule(owner, log_id).lead_minutes == 30
    assert service.get_rule(other, log_id) is None
    now = datetime(2026, 10, 1, 22, 35, tzinfo=timezone.utc)
    assert service.due(other, now) == ()
    due = service.due(owner, now)
    assert len(due) == 1
    assert due[0].title == "Antibiotic for Max"
    assert service.mark_delivered(owner, due[0], now)
    assert service.due(owner, now) == ()
    assert not service.mark_delivered(owner, due[0], now)
    assert service.recent_deliveries(other) == ()
    assert service.recent_deliveries(owner)[0].title == "Antibiotic for Max"
    storage.close()

    storage = Storage(path)
    service = MedicineReminderService(storage)
    assert service.due(owner, now) == ()
    MedicineService(storage).delete_log(owner, log_id)
    assert service.recent_deliveries(owner) == ()
    storage.close()
