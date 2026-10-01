"""Deterministic, opt-in calendar reminder rules and delivery claims."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import and_, or_, select
from sqlalchemy.dialects.sqlite import insert

from solar_forge_desktop.calendar import _event, occurrences
from solar_forge_desktop.household_access import can_read, member_ids, require_actor
from solar_forge_desktop.storage import (
    CalendarEvent,
    CalendarReminder,
    CalendarReminderDelivery,
    Storage,
    utc_now,
)

LEAD_MINUTES = (0, 5, 15, 30, 60, 1440)
MISSED_WINDOW = timedelta(hours=24)


@dataclass(frozen=True)
class DueReminder:
    reminder_id: int
    event_id: int
    title: str
    occurrence_at: datetime
    due_at: datetime


@dataclass(frozen=True)
class ReminderRule:
    lead_minutes: int
    timezone_id: str


@dataclass(frozen=True)
class DeliveredReminder:
    event_id: int
    title: str
    occurrence_at: datetime
    delivered_at: datetime
    timezone_id: str


def _zone(timezone_id: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone_id)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        raise ValueError("Choose a valid time zone.") from None


def _localize(wall_time: datetime, zone: ZoneInfo) -> datetime | None:
    """Use the first DST fold; skip wall times that do not exist locally."""
    local = wall_time.replace(tzinfo=zone, fold=0)
    round_trip = local.astimezone(timezone.utc).astimezone(zone)
    return local if round_trip.replace(tzinfo=None) == wall_time else None


class CalendarReminderService:
    def __init__(self, storage: Storage):
        self.storage = storage

    def set_rule(self, profile_id: int, event_id: int, lead_minutes: int,
                 timezone_id: str) -> int:
        if lead_minutes not in LEAD_MINUTES:
            raise ValueError("Choose a supported reminder lead time.")
        _zone(timezone_id)
        with self.storage.sessions.begin() as session:
            require_actor(session, profile_id)
            event = session.get(CalendarEvent, event_id)
            if event is None or not can_read(
                session, profile_id, event.profile_id, event.visibility
            ):
                raise ValueError("Calendar event not found.")
            if event.all_day:
                raise ValueError("All-day event reminders are not supported yet.")
            rule = session.scalar(select(CalendarReminder).where(
                CalendarReminder.profile_id == profile_id,
                CalendarReminder.event_id == event_id,
            ))
            if rule is None:
                rule = CalendarReminder(profile_id=profile_id, event_id=event_id)
                session.add(rule)
            rule.lead_minutes = lead_minutes
            rule.timezone_id = timezone_id
            session.flush()
            return rule.id

    def remove_rule(self, profile_id: int, event_id: int) -> None:
        with self.storage.sessions.begin() as session:
            require_actor(session, profile_id)
            rule = session.scalar(select(CalendarReminder).where(
                CalendarReminder.profile_id == profile_id,
                CalendarReminder.event_id == event_id,
            ))
            if rule is not None:
                session.delete(rule)

    def get_rule(self, profile_id: int, event_id: int) -> ReminderRule | None:
        with self.storage.sessions() as session:
            require_actor(session, profile_id)
            rule = session.scalar(select(CalendarReminder).where(
                CalendarReminder.profile_id == profile_id,
                CalendarReminder.event_id == event_id,
            ))
            if rule is None:
                return None
            event = session.get(CalendarEvent, event_id)
            if event is None or not can_read(
                session, profile_id, event.profile_id, event.visibility
            ):
                return None
            return ReminderRule(rule.lead_minutes, rule.timezone_id)

    def recent_deliveries(self, profile_id: int, limit: int = 5) -> tuple[DeliveredReminder, ...]:
        if not 1 <= limit <= 50:
            raise ValueError("Choose between 1 and 50 reminders.")
        with self.storage.sessions() as session:
            household_profiles = member_ids(session, profile_id)
            rows = session.execute(select(
                CalendarReminderDelivery, CalendarReminder, CalendarEvent,
            ).join(
                CalendarReminder,
                CalendarReminderDelivery.reminder_id == CalendarReminder.id,
            ).join(
                CalendarEvent, CalendarReminder.event_id == CalendarEvent.id,
            ).where(
                CalendarReminder.profile_id == profile_id,
                or_(CalendarEvent.profile_id == profile_id, and_(
                    CalendarEvent.visibility == "household",
                    CalendarEvent.profile_id.in_(household_profiles),
                )),
            ).order_by(CalendarReminderDelivery.delivered_at.desc()).limit(limit)).all()
            return tuple(
                DeliveredReminder(
                    event.id, event.title, datetime.fromisoformat(delivery.occurrence_at),
                    datetime.fromisoformat(delivery.delivered_at), rule.timezone_id,
                ) for delivery, rule, event in rows
            )

    def due(self, profile_id: int, now: datetime) -> tuple[DueReminder, ...]:
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Reminder clock must include a time zone.")
        now_utc = now.astimezone(timezone.utc)
        with self.storage.sessions() as session:
            require_actor(session, profile_id)
            rules = session.scalars(select(CalendarReminder).where(
                CalendarReminder.profile_id == profile_id
            )).all()
            result: list[DueReminder] = []
            for rule in rules:
                event = session.get(CalendarEvent, rule.event_id)
                if event is None or event.all_day or not can_read(
                    session, profile_id, event.profile_id, event.visibility
                ):
                    continue
                zone = _zone(rule.timezone_id)
                local_now = now_utc.astimezone(zone)
                first = (local_now - MISSED_WINDOW).date()
                last = (local_now + timedelta(days=2)).date()
                delivered = set(session.scalars(select(
                    CalendarReminderDelivery.occurrence_at
                ).where(CalendarReminderDelivery.reminder_id == rule.id)))
                for occurrence in occurrences(_event(event), first, last):
                    wall = occurrence.starts_at
                    if wall.isoformat() in delivered:
                        continue
                    local = _localize(wall, zone)
                    if local is None:
                        continue
                    due_at = (local.astimezone(timezone.utc)
                              - timedelta(minutes=rule.lead_minutes)).astimezone(zone)
                    if now_utc - MISSED_WINDOW < due_at.astimezone(timezone.utc) <= now_utc:
                        result.append(DueReminder(
                            rule.id, event.id, event.title, wall, due_at,
                        ))
            return tuple(sorted(result, key=lambda item: (item.due_at, item.reminder_id)))

    def mark_delivered(self, profile_id: int, reminder: DueReminder,
                       now: datetime) -> bool:
        if reminder not in self.due(profile_id, now):
            return False
        with self.storage.sessions.begin() as session:
            statement = insert(CalendarReminderDelivery).values(
                reminder_id=reminder.reminder_id,
                occurrence_at=reminder.occurrence_at.isoformat(),
                delivered_at=utc_now(),
            ).on_conflict_do_nothing(index_elements=["reminder_id", "occurrence_at"])
            return session.execute(statement).rowcount == 1
