"""Profile-scoped recurring home maintenance with calendar-safe dates."""

import calendar
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select

from solar_forge_desktop.storage import MaintenanceItem, Profile, Storage, utc_now

CATEGORIES = ("General", "Appliances", "Cleaning", "Exterior", "Safety", "Vehicle")
UNITS = ("days", "weeks", "months", "years")


@dataclass(frozen=True)
class MaintenanceEntry:
    id: int
    name: str
    category: str
    next_due_date: date
    recurrence_interval: int
    recurrence_unit: str
    estimated_cost: Decimal | None
    notes: str | None
    last_completed_date: date | None
    status: str


@dataclass(frozen=True)
class MaintenanceView:
    total: int
    overdue: int
    due_soon: int
    items: tuple[MaintenanceEntry, ...]


def advance_date(due: date, interval: int, unit: str) -> date:
    """Advance one scheduled occurrence, clipping invalid month-end days."""
    if unit == "days":
        return due + timedelta(days=interval)
    if unit == "weeks":
        return due + timedelta(weeks=interval)
    months = interval if unit == "months" else interval * 12
    index = due.month - 1 + months
    year, month = due.year + index // 12, index % 12 + 1
    return date(year, month, min(due.day, calendar.monthrange(year, month)[1]))


def _date(value: date) -> str:
    if not isinstance(value, date) or isinstance(value, datetime):
        raise ValueError("A valid next due date is required.")
    return value.isoformat()


def _cost(raw: str | None) -> str | None:
    if raw is None or raw == "":
        return None
    try:
        value = Decimal(raw.strip())
    except (AttributeError, InvalidOperation) as exc:
        raise ValueError("Estimated cost must be zero or greater.") from exc
    if not value.is_finite() or value < 0:
        raise ValueError("Estimated cost must be zero or greater.")
    try:
        return str(value.quantize(Decimal("0.01")))
    except InvalidOperation as exc:
        raise ValueError("Estimated cost is too large.") from exc


class MaintenanceService:
    def __init__(self, storage: Storage):
        self.storage = storage

    def view(self, profile_id: int, today: date | None = None,
             limit: int = 200) -> MaintenanceView:
        current = today or date.today()
        _date(current)
        if not 1 <= limit <= 500:
            raise ValueError("Maintenance history limit must be between 1 and 500.")
        with self.storage.sessions() as session:
            if session.get(Profile, profile_id) is None:
                raise ValueError("Profile not found.")
            total = session.scalar(select(func.count()).select_from(MaintenanceItem).where(
                MaintenanceItem.profile_id == profile_id
            ))
            overdue = session.scalar(select(func.count()).select_from(MaintenanceItem).where(
                MaintenanceItem.profile_id == profile_id,
                MaintenanceItem.next_due_date < current.isoformat(),
            ))
            soon_end = (current + timedelta(days=14)).isoformat()
            soon = session.scalar(select(func.count()).select_from(MaintenanceItem).where(
                MaintenanceItem.profile_id == profile_id,
                MaintenanceItem.next_due_date >= current.isoformat(),
                MaintenanceItem.next_due_date <= soon_end,
            ))
            rows = session.scalars(select(MaintenanceItem).where(
                MaintenanceItem.profile_id == profile_id
            ).order_by(MaintenanceItem.next_due_date, MaintenanceItem.name,
                       MaintenanceItem.id).limit(limit)).all()
            items = tuple(MaintenanceEntry(
                row.id, row.name, row.category, date.fromisoformat(row.next_due_date),
                row.recurrence_interval, row.recurrence_unit,
                Decimal(row.estimated_cost) if row.estimated_cost is not None else None,
                row.notes,
                date.fromisoformat(row.last_completed_date) if row.last_completed_date else None,
                "overdue" if row.next_due_date < current.isoformat() else (
                    "soon" if row.next_due_date <= soon_end else "upcoming"
                ),
            ) for row in rows)
            return MaintenanceView(total, overdue, soon, items)

    def add(self, profile_id: int, name: str, category: str, next_due: date,
            interval: int, unit: str, cost_raw: str | None = None,
            notes: str | None = None) -> int:
        due = _date(next_due)
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Maintenance item name is required.")
        name = name.strip()
        if len(name) > 150:
            raise ValueError("Maintenance item name must be 150 characters or fewer.")
        if category not in CATEGORIES:
            raise ValueError("Choose a valid category.")
        if unit not in UNITS:
            raise ValueError("Choose a valid repeat unit.")
        if type(interval) is not int or not 1 <= interval <= 999:
            raise ValueError("The repeat interval must be between 1 and 999.")
        cost = _cost(cost_raw)
        if notes is not None and not isinstance(notes, str):
            raise ValueError("Notes must be text.")
        with self.storage.sessions.begin() as session:
            if session.get(Profile, profile_id) is None:
                raise ValueError("Profile not found.")
            item = MaintenanceItem(
                profile_id=profile_id, name=name, category=category,
                next_due_date=due, recurrence_interval=interval,
                recurrence_unit=unit, estimated_cost=cost,
                notes=(notes or "").strip() or None,
                last_completed_date=None, created_at=utc_now(),
            )
            session.add(item)
            session.flush()
            return item.id

    def complete(self, profile_id: int, item_id: int,
                 today: date | None = None) -> date:
        completed = today or date.today()
        _date(completed)
        with self.storage.sessions.begin() as session:
            item = session.scalar(select(MaintenanceItem).where(
                MaintenanceItem.id == item_id, MaintenanceItem.profile_id == profile_id
            ))
            if item is None:
                raise ValueError("Maintenance item not found.")
            due = date.fromisoformat(item.next_due_date)
            next_due = advance_date(due, item.recurrence_interval, item.recurrence_unit)
            while next_due <= completed:
                next_due = advance_date(next_due, item.recurrence_interval,
                                        item.recurrence_unit)
            item.last_completed_date = completed.isoformat()
            item.next_due_date = next_due.isoformat()
            return next_due

    def delete(self, profile_id: int, item_id: int) -> None:
        with self.storage.sessions.begin() as session:
            item = session.scalar(select(MaintenanceItem).where(
                MaintenanceItem.id == item_id, MaintenanceItem.profile_id == profile_id
            ))
            if item is None:
                raise ValueError("Maintenance item not found.")
            session.delete(item)
