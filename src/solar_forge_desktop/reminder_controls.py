"""Shared lead-time and IANA time-zone selectors for reminder forms."""

from functools import lru_cache
from zoneinfo import available_timezones

from PySide6.QtCore import QTimeZone
from PySide6.QtWidgets import QComboBox

from solar_forge_desktop.reminders import LEAD_MINUTES

LEAD_LABELS = (
    "At scheduled time", "5 minutes before", "15 minutes before",
    "30 minutes before", "1 hour before", "1 day before",
)


@lru_cache(maxsize=1)
def time_zones() -> tuple[str, ...]:
    return tuple(sorted(available_timezones() | {"UTC"}))


def system_time_zone() -> str:
    zone = bytes(QTimeZone.systemTimeZoneId()).decode() or "UTC"
    return zone if zone in time_zones() else "UTC"


def lead_selector(accessible_name: str) -> QComboBox:
    field = QComboBox()
    field.setAccessibleName(accessible_name)
    for minutes, label in zip(LEAD_MINUTES, LEAD_LABELS, strict=True):
        field.addItem(label, minutes)
    return field


def time_zone_selector(accessible_name: str) -> QComboBox:
    field = QComboBox()
    field.setAccessibleName(accessible_name)
    field.addItems(time_zones())
    field.setCurrentIndex(field.findText(system_time_zone()))
    return field
