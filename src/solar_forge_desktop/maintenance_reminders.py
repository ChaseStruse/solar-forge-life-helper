"""Opt-in reminders for recurring home maintenance dates."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert

from solar_forge_desktop.household_access import require_actor
from solar_forge_desktop.reminders import MISSED_WINDOW, _localize, _zone
from solar_forge_desktop.storage import (
    MaintenanceItem,
    MaintenanceReminder,
    MaintenanceReminderDelivery,
    Storage,
    utc_now,
)

LEAD_DAYS = (0, 1, 7)


@dataclass(frozen=True)
class MaintenanceReminderRule:
    lead_days: int
    time_of_day: time
    timezone_id: str


@dataclass(frozen=True)
class DueMaintenanceReminder:
    reminder_id: int
    item_id: int
    title: str
    occurrence_at: datetime
    due_at: datetime


@dataclass(frozen=True)
class DeliveredMaintenanceReminder:
    item_id: int
    title: str
    delivered_at: datetime
    timezone_id: str


class MaintenanceReminderService:
    def __init__(self, storage: Storage):
        self.storage = storage

    def set_rule(self, profile_id: int, item_id: int, lead_days: int,
                 time_of_day: time, timezone_id: str) -> int:
        if lead_days not in LEAD_DAYS:
            raise ValueError("Choose a supported reminder lead time.")
        if not isinstance(time_of_day, time) or time_of_day.tzinfo is not None:
            raise ValueError("Choose a local reminder time.")
        _zone(timezone_id)
        with self.storage.sessions.begin() as session:
            require_actor(session, profile_id)
            item = session.get(MaintenanceItem, item_id)
            if item is None or item.profile_id != profile_id:
                raise ValueError("Maintenance item not found.")
            rule = session.scalar(select(MaintenanceReminder).where(
                MaintenanceReminder.profile_id == profile_id,
                MaintenanceReminder.item_id == item_id,
            ))
            if rule is None:
                rule = MaintenanceReminder(profile_id=profile_id, item_id=item_id)
                session.add(rule)
            rule.lead_days = lead_days
            rule.time_of_day = time_of_day.strftime("%H:%M")
            rule.timezone_id = timezone_id
            session.flush()
            return rule.id

    def remove_rule(self, profile_id: int, item_id: int) -> None:
        with self.storage.sessions.begin() as session:
            require_actor(session, profile_id)
            rule = session.scalar(select(MaintenanceReminder).where(
                MaintenanceReminder.profile_id == profile_id,
                MaintenanceReminder.item_id == item_id,
            ))
            if rule is not None:
                session.delete(rule)

    def get_rule(self, profile_id: int, item_id: int) -> MaintenanceReminderRule | None:
        with self.storage.sessions() as session:
            require_actor(session, profile_id)
            rule = session.scalar(select(MaintenanceReminder).join(
                MaintenanceItem, MaintenanceReminder.item_id == MaintenanceItem.id,
            ).where(
                MaintenanceReminder.profile_id == profile_id,
                MaintenanceReminder.item_id == item_id,
                MaintenanceItem.profile_id == profile_id,
            ))
            return (MaintenanceReminderRule(
                rule.lead_days, time.fromisoformat(rule.time_of_day), rule.timezone_id,
            ) if rule else None)

    def due(self, profile_id: int, now: datetime) -> tuple[DueMaintenanceReminder, ...]:
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Reminder clock must include a time zone.")
        now_utc = now.astimezone(timezone.utc)
        with self.storage.sessions() as session:
            require_actor(session, profile_id)
            rows = session.execute(select(MaintenanceReminder, MaintenanceItem).join(
                MaintenanceItem, MaintenanceReminder.item_id == MaintenanceItem.id,
            ).where(
                MaintenanceReminder.profile_id == profile_id,
                MaintenanceItem.profile_id == profile_id,
            )).all()
            result = []
            for rule, item in rows:
                delivered = session.scalar(select(MaintenanceReminderDelivery.id).where(
                    MaintenanceReminderDelivery.reminder_id == rule.id,
                    MaintenanceReminderDelivery.next_due_date == item.next_due_date,
                ))
                if delivered is not None:
                    continue
                occurrence = datetime.combine(
                    date.fromisoformat(item.next_due_date), time.fromisoformat(rule.time_of_day),
                )
                trigger_wall = occurrence - timedelta(days=rule.lead_days)
                local = _localize(trigger_wall, _zone(rule.timezone_id))
                if local is None:
                    continue
                if now_utc - MISSED_WINDOW < local.astimezone(timezone.utc) <= now_utc:
                    result.append(DueMaintenanceReminder(
                        rule.id, item.id, item.name, occurrence, local,
                    ))
            return tuple(sorted(result, key=lambda entry: (entry.due_at, entry.reminder_id)))

    def mark_delivered(self, profile_id: int, reminder: DueMaintenanceReminder,
                       now: datetime) -> bool:
        if reminder not in self.due(profile_id, now):
            return False
        with self.storage.sessions.begin() as session:
            statement = insert(MaintenanceReminderDelivery).values(
                reminder_id=reminder.reminder_id,
                next_due_date=reminder.occurrence_at.date().isoformat(),
                delivered_at=utc_now(),
            ).on_conflict_do_nothing(index_elements=["reminder_id", "next_due_date"])
            return session.execute(statement).rowcount == 1

    def recent_deliveries(self, profile_id: int, limit: int = 5
                          ) -> tuple[DeliveredMaintenanceReminder, ...]:
        if not 1 <= limit <= 50:
            raise ValueError("Choose between 1 and 50 reminders.")
        with self.storage.sessions() as session:
            require_actor(session, profile_id)
            rows = session.execute(select(
                MaintenanceReminderDelivery, MaintenanceReminder, MaintenanceItem,
            ).join(MaintenanceReminder,
                   MaintenanceReminderDelivery.reminder_id == MaintenanceReminder.id)
                .join(MaintenanceItem, MaintenanceReminder.item_id == MaintenanceItem.id)
                .where(MaintenanceReminder.profile_id == profile_id,
                       MaintenanceItem.profile_id == profile_id)
                .order_by(MaintenanceReminderDelivery.delivered_at.desc())
                .limit(limit)).all()
            return tuple(DeliveredMaintenanceReminder(
                item.id, item.name, datetime.fromisoformat(delivery.delivered_at),
                rule.timezone_id,
            ) for delivery, rule, item in rows)
