"""Opt-in next-dose reminders for private medicine logs."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert

from solar_forge_desktop.household_access import require_actor
from solar_forge_desktop.reminders import (
    LEAD_MINUTES,
    MISSED_WINDOW,
    ReminderRule,
    _localize,
    _zone,
)
from solar_forge_desktop.storage import (
    MedicineLog,
    MedicineReminder,
    MedicineReminderDelivery,
    Storage,
    utc_now,
)


@dataclass(frozen=True)
class DueMedicineReminder:
    reminder_id: int
    log_id: int
    title: str
    occurrence_at: datetime
    due_at: datetime


@dataclass(frozen=True)
class DeliveredMedicineReminder:
    log_id: int
    title: str
    delivered_at: datetime
    timezone_id: str


class MedicineReminderService:
    def __init__(self, storage: Storage):
        self.storage = storage

    def set_rule(self, profile_id: int, log_id: int, lead_minutes: int,
                 timezone_id: str) -> int:
        if lead_minutes not in LEAD_MINUTES:
            raise ValueError("Choose a supported reminder lead time.")
        _zone(timezone_id)
        with self.storage.sessions.begin() as session:
            require_actor(session, profile_id)
            log = session.get(MedicineLog, log_id)
            if log is None or log.profile_id != profile_id:
                raise ValueError("Medicine log entry not found.")
            rule = session.scalar(select(MedicineReminder).where(
                MedicineReminder.profile_id == profile_id,
                MedicineReminder.log_id == log_id,
            ))
            if rule is None:
                rule = MedicineReminder(profile_id=profile_id, log_id=log_id)
                session.add(rule)
            rule.lead_minutes = lead_minutes
            rule.timezone_id = timezone_id
            session.flush()
            return rule.id

    def get_rule(self, profile_id: int, log_id: int) -> ReminderRule | None:
        with self.storage.sessions() as session:
            require_actor(session, profile_id)
            rule = session.scalar(select(MedicineReminder).join(
                MedicineLog, MedicineReminder.log_id == MedicineLog.id,
            ).where(
                MedicineReminder.profile_id == profile_id,
                MedicineReminder.log_id == log_id,
                MedicineLog.profile_id == profile_id,
            ))
            return ReminderRule(rule.lead_minutes, rule.timezone_id) if rule else None

    def remove_rule(self, profile_id: int, log_id: int) -> None:
        with self.storage.sessions.begin() as session:
            require_actor(session, profile_id)
            rule = session.scalar(select(MedicineReminder).where(
                MedicineReminder.profile_id == profile_id,
                MedicineReminder.log_id == log_id,
            ))
            if rule is not None:
                session.delete(rule)

    def due(self, profile_id: int, now: datetime) -> tuple[DueMedicineReminder, ...]:
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Reminder clock must include a time zone.")
        now_utc = now.astimezone(timezone.utc)
        with self.storage.sessions() as session:
            require_actor(session, profile_id)
            rows = session.execute(select(MedicineReminder, MedicineLog).join(
                MedicineLog, MedicineReminder.log_id == MedicineLog.id,
            ).where(
                MedicineReminder.profile_id == profile_id,
                MedicineLog.profile_id == profile_id,
            )).all()
            result = []
            for rule, log in rows:
                delivered = session.scalar(select(MedicineReminderDelivery.id).where(
                    MedicineReminderDelivery.reminder_id == rule.id,
                    MedicineReminderDelivery.next_due_at == log.next_due_at,
                ))
                if delivered is not None:
                    continue
                occurrence = datetime.fromisoformat(log.next_due_at)
                local = _localize(occurrence, _zone(rule.timezone_id))
                if local is None:
                    continue
                due_at = local - timedelta(minutes=rule.lead_minutes)
                if now_utc - MISSED_WINDOW < due_at.astimezone(timezone.utc) <= now_utc:
                    result.append(DueMedicineReminder(
                        rule.id, log.id, f"{log.medicine_name} for {log.recipient}",
                        occurrence, due_at,
                    ))
            return tuple(sorted(result, key=lambda item: (item.due_at, item.reminder_id)))

    def mark_delivered(self, profile_id: int, reminder: DueMedicineReminder,
                       now: datetime) -> bool:
        if reminder not in self.due(profile_id, now):
            return False
        with self.storage.sessions.begin() as session:
            statement = insert(MedicineReminderDelivery).values(
                reminder_id=reminder.reminder_id,
                next_due_at=reminder.occurrence_at.isoformat(timespec="minutes"),
                delivered_at=utc_now(),
            ).on_conflict_do_nothing(index_elements=["reminder_id", "next_due_at"])
            return session.execute(statement).rowcount == 1

    def recent_deliveries(self, profile_id: int, limit: int = 5
                          ) -> tuple[DeliveredMedicineReminder, ...]:
        if not 1 <= limit <= 50:
            raise ValueError("Choose between 1 and 50 reminders.")
        with self.storage.sessions() as session:
            require_actor(session, profile_id)
            rows = session.execute(select(
                MedicineReminderDelivery, MedicineReminder, MedicineLog,
            ).join(
                MedicineReminder,
                MedicineReminderDelivery.reminder_id == MedicineReminder.id,
            ).join(
                MedicineLog, MedicineReminder.log_id == MedicineLog.id,
            ).where(
                MedicineReminder.profile_id == profile_id,
                MedicineLog.profile_id == profile_id,
            ).order_by(MedicineReminderDelivery.delivered_at.desc()).limit(limit)).all()
            return tuple(DeliveredMedicineReminder(
                log.id, f"{log.medicine_name} for {log.recipient}",
                datetime.fromisoformat(delivery.delivered_at), rule.timezone_id,
            ) for delivery, rule, log in rows)
