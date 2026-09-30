"""Profile-scoped calendar events and bounded recurring occurrence expansion."""

import calendar as months
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from sqlalchemy import select

from solar_forge_desktop.storage import CalendarEvent, Profile, Storage, utc_now

RECURRENCES = ("none", "daily", "weekly", "monthly", "yearly")
TAG_COLORS = ("#8b5cf6", "#ec4899", "#06b6d4", "#10b981", "#f59e0b", "#6366f1")


@dataclass(frozen=True)
class Event:
    id: int
    title: str
    description: str | None
    category: str
    starts_at: datetime
    ends_at: datetime
    all_day: bool
    recurrence: str
    recurrence_until: date | None


@dataclass(frozen=True)
class Occurrence:
    event: Event
    starts_at: datetime
    ends_at: datetime


@dataclass(frozen=True)
class CalendarView:
    mode: str
    selected: date
    visible_start: date
    visible_end: date
    previous: date
    next: date
    label: str
    days: tuple[tuple[date, tuple[Occurrence, ...]], ...]
    categories: tuple[str, ...]

    @property
    def event_count(self) -> int:
        return sum(len(items) for _, items in self.days)


def tag_color(category: str) -> str:
    return TAG_COLORS[sum(ord(char) for char in category.casefold()) % len(TAG_COLORS)]


def shift_month(day: date, offset: int) -> date:
    index = day.year * 12 + day.month - 1 + offset
    year, month = divmod(index, 12)
    return date(year, month + 1, 1)


def _occurrence_start(start: datetime, recurrence: str, index: int) -> datetime:
    if recurrence == "daily":
        return start + timedelta(days=index)
    if recurrence == "weekly":
        return start + timedelta(weeks=index)
    if recurrence == "monthly":
        shifted = shift_month(start.date(), index)
        return start.replace(year=shifted.year, month=shifted.month,
                             day=min(start.day, months.monthrange(shifted.year, shifted.month)[1]))
    year = start.year + index
    return start.replace(year=year, day=min(start.day, months.monthrange(year, start.month)[1]))


def occurrences(event: Event, first: date, last: date) -> tuple[Occurrence, ...]:
    if event.recurrence == "none":
        return (Occurrence(event, event.starts_at, event.ends_at),) if (
            first <= event.starts_at.date() <= last
        ) else ()
    if event.starts_at.date() > last:
        return ()
    if event.recurrence in ("daily", "weekly"):
        days = (first - event.starts_at.date()).days
        index = max(0, days // (1 if event.recurrence == "daily" else 7) - 1)
    elif event.recurrence == "monthly":
        index = max(0, (first.year - event.starts_at.year) * 12
                    + first.month - event.starts_at.month - 1)
    else:
        index = max(0, first.year - event.starts_at.year - 1)
    result = []
    duration = event.ends_at - event.starts_at
    while True:
        start = _occurrence_start(event.starts_at, event.recurrence, index)
        if start.date() > last or (event.recurrence_until
                                   and start.date() > event.recurrence_until):
            break
        if start.date() >= first:
            result.append(Occurrence(event, start, start + duration))
        index += 1
    return tuple(result)


def _event(row: CalendarEvent) -> Event:
    return Event(row.id, row.title, row.description, row.category,
                 datetime.fromisoformat(row.starts_at), datetime.fromisoformat(row.ends_at),
                 row.all_day, row.recurrence,
                 date.fromisoformat(row.recurrence_until) if row.recurrence_until else None)


def _bounds(selected: date, mode: str) -> tuple[date, date, date, date, str]:
    if mode == "week":
        first = selected - timedelta(days=selected.weekday())
        last = first + timedelta(days=6)
        label = (f"{first:%b} {first.day} - {last.day}, {last.year}"
                 if first.month == last.month else
                 f"{first:%b} {first.day} - {last:%b} {last.day}, {last.year}")
        return first, last, first - timedelta(days=7), first + timedelta(days=7), label
    month_start = selected.replace(day=1)
    month_end = shift_month(month_start, 1) - timedelta(days=1)
    first = month_start - timedelta(days=month_start.weekday())
    last = month_end + timedelta(days=6 - month_end.weekday())
    return first, last, shift_month(month_start, -1), shift_month(month_start, 1), \
        month_start.strftime("%B %Y")


class CalendarService:
    def __init__(self, storage: Storage):
        self.storage = storage

    def view(self, profile_id: int, selected: date | None = None,
             mode: str = "month") -> CalendarView:
        selected = selected or date.today()
        if not isinstance(selected, date) or isinstance(selected, datetime):
            raise ValueError("Choose a valid calendar date.")
        if mode not in ("month", "week"):
            raise ValueError("Choose a valid calendar view.")
        first, last, previous, next_date, label = _bounds(selected, mode)
        with self.storage.sessions() as session:
            if session.get(Profile, profile_id) is None:
                raise ValueError("Profile not found.")
            rows = session.scalars(select(CalendarEvent).where(
                CalendarEvent.profile_id == profile_id,
                CalendarEvent.starts_at < datetime.combine(last + timedelta(days=1),
                                                          time.min).isoformat(),
            ).order_by(CalendarEvent.starts_at, CalendarEvent.id)).all()
            events = tuple(map(_event, rows))
        by_day: dict[date, list[Occurrence]] = {}
        for event in events:
            for occurrence in occurrences(event, first, last):
                by_day.setdefault(occurrence.starts_at.date(), []).append(occurrence)
        days = []
        day = first
        while day <= last:
            items = by_day.get(day, [])
            items.sort(key=lambda item: (not item.event.all_day, item.starts_at,
                                         item.event.id))
            days.append((day, tuple(items)))
            day += timedelta(days=1)
        return CalendarView(mode, selected, first, last, previous, next_date,
                            label, tuple(days), tuple(sorted({event.category for event in events})))

    def get(self, profile_id: int, event_id: int) -> Event:
        with self.storage.sessions() as session:
            row = session.scalar(select(CalendarEvent).where(
                CalendarEvent.id == event_id, CalendarEvent.profile_id == profile_id))
            if row is None:
                raise ValueError("Calendar event not found.")
            return _event(row)

    def save(self, profile_id: int, title: str, description: str | None, category: str,
             starts_at: datetime, ends_at: datetime, all_day: bool = False,
             recurrence: str = "none", recurrence_until: date | None = None,
             event_id: int | None = None) -> int:
        title = title.strip() if isinstance(title, str) else ""
        category = category.strip() if isinstance(category, str) else ""
        description = description.strip() if isinstance(description, str) else ""
        if not title or len(title) > 150:
            raise ValueError("Event title is required and must be 150 characters or fewer.")
        if len(description) > 2000:
            raise ValueError("Description must be 2000 characters or fewer.")
        if not category or len(category) > 50:
            raise ValueError("Event tag is required and must be 50 characters or fewer.")
        if not isinstance(starts_at, datetime) or not isinstance(ends_at, datetime) \
                or starts_at.tzinfo or ends_at.tzinfo:
            raise ValueError("Choose valid event start and end dates and times.")
        if ends_at <= starts_at:
            raise ValueError("Event end must be after its start.")
        if recurrence not in RECURRENCES:
            raise ValueError("Choose a valid repeat option.")
        if recurrence_until is not None:
            if not isinstance(recurrence_until, date) \
                    or isinstance(recurrence_until, datetime):
                raise ValueError("Choose a valid repeat-until date.")
            if recurrence == "none":
                raise ValueError("Choose a repeat option before setting a repeat-until date.")
            if recurrence_until < starts_at.date():
                raise ValueError("Repeat-until date cannot be before the event starts.")
        with self.storage.sessions.begin() as session:
            if session.get(Profile, profile_id) is None:
                raise ValueError("Profile not found.")
            if event_id is None:
                row = CalendarEvent(profile_id=profile_id, created_at=utc_now())
                session.add(row)
            else:
                row = session.scalar(select(CalendarEvent).where(
                    CalendarEvent.id == event_id, CalendarEvent.profile_id == profile_id))
                if row is None:
                    raise ValueError("Calendar event not found.")
            row.title, row.description, row.category = title, description or None, category
            row.starts_at, row.ends_at = starts_at.isoformat(), ends_at.isoformat()
            row.all_day, row.recurrence = all_day, recurrence
            row.recurrence_until = recurrence_until.isoformat() if recurrence_until else None
            session.flush()
            return row.id

    def delete(self, profile_id: int, event_id: int) -> None:
        with self.storage.sessions.begin() as session:
            row = session.scalar(select(CalendarEvent).where(
                CalendarEvent.id == event_id, CalendarEvent.profile_id == profile_id))
            if row is None:
                raise ValueError("Calendar event not found.")
            session.delete(row)
