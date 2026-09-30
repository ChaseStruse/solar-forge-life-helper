"""Calendar parity, recurrence edge cases, ownership, and schema upgrade."""

import sqlite3
from contextlib import closing
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from solar_forge_desktop.calendar import CalendarService, occurrences, tag_color
from solar_forge_desktop.storage import Storage


def moment(day: str, clock: str = "09:00") -> datetime:
    return datetime.fromisoformat(f"{day}T{clock}")


def test_event_crud_views_and_profile_ownership(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "calendar.db")
    first = storage.default_profile_id()
    second = storage.create_profile("Other")
    service = CalendarService(storage)
    event_id = service.save(first, " Dentist ", " Bring card ", " Health ",
                            moment("2026-09-28"), moment("2026-09-28", "10:00"))
    week = service.view(first, date(2026, 9, 28), "week")
    assert week.label == "Sep 28 - Oct 4, 2026"
    assert week.event_count == 1
    assert week.days[0][1][0].event.title == "Dentist"
    assert week.categories == ("Health",)
    assert service.view(second, date(2026, 9, 28)).event_count == 0
    with pytest.raises(ValueError, match="not found"):
        service.get(second, event_id)
    with pytest.raises(ValueError, match="not found"):
        service.delete(second, event_id)
    service.save(first, "Updated", None, "Personal", moment("2026-10-01"),
                 moment("2026-10-01", "10:00"), event_id=event_id)
    assert service.get(first, event_id).title == "Updated"
    month = service.view(first, date(2026, 9, 28))
    assert (month.visible_start, month.visible_end) == (date(2026, 8, 31), date(2026, 10, 4))
    assert month.event_count == 1
    service.delete(first, event_id)
    assert service.view(first, date(2026, 9, 28)).event_count == 0
    storage.close()


def test_recurrence_clamps_to_original_month_end_and_leap_day(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "calendar.db")
    service = CalendarService(storage)
    profile = storage.default_profile_id()
    monthly = service.save(profile, "Bills", None, "Home", moment("2026-01-31"),
                           moment("2026-01-31", "10:00"), recurrence="monthly",
                           recurrence_until=date(2026, 4, 30))
    yearly = service.save(profile, "Leap", None, "Personal", moment("2024-02-29"),
                          moment("2024-02-29", "10:00"), recurrence="yearly")
    jan_event = service.get(profile, monthly)
    starts = [item.starts_at.date() for item in occurrences(
        jan_event, date(2026, 1, 1), date(2026, 5, 31))]
    assert starts == [date(2026, 1, 31), date(2026, 2, 28),
                      date(2026, 3, 31), date(2026, 4, 30)]
    leap = service.get(profile, yearly)
    assert [item.starts_at.date() for item in occurrences(
        leap, date(2025, 1, 1), date(2028, 12, 31))] == [
            date(2025, 2, 28), date(2026, 2, 28), date(2027, 2, 28), date(2028, 2, 29)]
    daily = service.save(profile, "Day", None, "Routine", moment("2020-01-01"),
                         moment("2020-01-01", "10:00"), recurrence="daily")
    assert service.view(profile, date(2026, 9, 28), "week").event_count == 7
    assert len(occurrences(service.get(profile, daily), date(2026, 9, 28),
                           date(2026, 10, 4))) == 7
    assert tag_color("Personal") == tag_color("personal")
    storage.close()


def test_all_day_duration_and_validation(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "calendar.db")
    service = CalendarService(storage)
    profile = storage.default_profile_id()
    event_id = service.save(profile, "Trip", None, "Travel", moment("2026-09-28", "00:00"),
                            moment("2026-10-01", "00:00"), all_day=True,
                            recurrence="weekly", recurrence_until=date(2026, 10, 5))
    item = service.view(profile, date(2026, 10, 5), "week").days[0][1][0]
    assert item.ends_at - item.starts_at == timedelta(days=3)
    for args, message in (
        (("", None, "Tag", moment("2026-09-28"), moment("2026-09-29")), "title"),
        (("A", None, "", moment("2026-09-28"), moment("2026-09-29")), "tag"),
        (("A", None, "Tag", moment("2026-09-29"), moment("2026-09-28")), "after"),
    ):
        with pytest.raises(ValueError, match=message):
            service.save(profile, *args)
    with pytest.raises(ValueError, match="Repeat-until"):
        service.save(profile, "A", None, "Tag", moment("2026-09-28"),
                     moment("2026-09-28", "10:00"), recurrence="daily",
                     recurrence_until=date(2026, 9, 27))
    with pytest.raises(ValueError, match="not found"):
        service.save(profile, "A", None, "Tag", moment("2026-09-28"),
                     moment("2026-09-28", "10:00"), event_id=event_id + 1)
    storage.close()


def test_invalid_calendar_inputs_and_future_series(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "calendar.db")
    service = CalendarService(storage)
    profile = storage.default_profile_id()
    with pytest.raises(ValueError, match="valid calendar date"):
        service.view(profile, datetime(2026, 9, 28))
    with pytest.raises(ValueError, match="valid calendar view"):
        service.view(profile, date(2026, 9, 28), "agenda")
    with pytest.raises(ValueError, match="Profile not found"):
        service.view(999, date(2026, 9, 28))
    start, end = moment("2026-09-28"), moment("2026-09-28", "10:00")
    invalid = (
        ({"description": "x" * 2001}, "Description"),
        ({"starts_at": date(2026, 9, 28)}, "valid event start"),
        ({"recurrence": "hourly"}, "valid repeat option"),
        ({"recurrence": "daily", "recurrence_until": datetime(2026, 9, 29)},
         "valid repeat-until"),
        ({"recurrence_until": date(2026, 9, 29)}, "repeat option"),
    )
    for overrides, message in invalid:
        fields = {"description": None, "starts_at": start, "ends_at": end}
        fields.update(overrides)
        with pytest.raises(ValueError, match=message):
            service.save(profile, "A", fields.pop("description"), "Tag", **fields)
    with pytest.raises(ValueError, match="Profile not found"):
        service.save(999, "A", None, "Tag", start, end)
    future = service.save(profile, "Future", None, "Tag", moment("2030-01-01"),
                          moment("2030-01-01", "10:00"), recurrence="daily")
    assert occurrences(service.get(profile, future), date(2026, 9, 28),
                       date(2026, 10, 4)) == ()
    storage.close()


def test_v12_upgrade_snapshot_and_missing_table(tmp_path: Path) -> None:
    path = tmp_path / "old.db"
    storage = Storage(path)
    profile = storage.default_profile_id()
    storage.close()
    with closing(sqlite3.connect(path)) as db:
        db.execute("DROP TABLE profile_settings")
        db.execute("DROP TABLE calendar_events")
        db.execute("PRAGMA user_version=12")
        db.commit()
    upgraded = Storage(path)
    assert CalendarService(upgraded).view(profile, date(2026, 9, 28)).event_count == 0
    upgraded.close()
    with closing(sqlite3.connect(path.with_name("old.db.pre-calendar-v12"))) as snapshot:
        assert snapshot.execute("PRAGMA user_version").fetchone()[0] == 12
        assert "calendar_events" not in {row[0] for row in snapshot.execute(
            "SELECT name FROM sqlite_master")}
    with closing(sqlite3.connect(path)) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 16
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        db.execute("DROP TABLE calendar_events")
        db.commit()
    with pytest.raises(RuntimeError, match="missing calendar tables"):
        Storage(path)
