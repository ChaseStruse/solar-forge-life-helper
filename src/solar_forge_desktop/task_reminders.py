"""Opt-in task reminders with per-member visibility and durable claims."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, or_, select
from sqlalchemy.dialects.sqlite import insert

from solar_forge_desktop.household_access import can_read, member_ids, require_actor
from solar_forge_desktop.reminders import (
    LEAD_MINUTES,
    MISSED_WINDOW,
    ReminderRule,
    _localize,
    _zone,
)
from solar_forge_desktop.storage import Storage, Task, TaskReminder, TaskReminderDelivery, utc_now


@dataclass(frozen=True)
class DueTaskReminder:
    reminder_id: int
    task_id: int
    title: str
    occurrence_at: datetime
    due_at: datetime


@dataclass(frozen=True)
class DeliveredTaskReminder:
    task_id: int
    title: str
    delivered_at: datetime
    timezone_id: str


class TaskReminderService:
    def __init__(self, storage: Storage):
        self.storage = storage

    def set_rule(self, profile_id: int, task_id: int, lead_minutes: int,
                 timezone_id: str) -> int:
        if lead_minutes not in LEAD_MINUTES:
            raise ValueError("Choose a supported reminder lead time.")
        _zone(timezone_id)
        with self.storage.sessions.begin() as session:
            require_actor(session, profile_id)
            task = session.get(Task, task_id)
            if task is None or not can_read(session, profile_id, task.profile_id, task.visibility):
                raise ValueError("Task not found.")
            if task.due_at is None:
                raise ValueError("Set a task due date before adding a reminder.")
            rule = session.scalar(select(TaskReminder).where(
                TaskReminder.profile_id == profile_id, TaskReminder.task_id == task_id,
            ))
            if rule is None:
                rule = TaskReminder(profile_id=profile_id, task_id=task_id)
                session.add(rule)
            rule.lead_minutes = lead_minutes
            rule.timezone_id = timezone_id
            session.flush()
            return rule.id

    def remove_rule(self, profile_id: int, task_id: int) -> None:
        with self.storage.sessions.begin() as session:
            require_actor(session, profile_id)
            rule = session.scalar(select(TaskReminder).where(
                TaskReminder.profile_id == profile_id, TaskReminder.task_id == task_id,
            ))
            if rule is not None:
                session.delete(rule)

    def get_rule(self, profile_id: int, task_id: int) -> ReminderRule | None:
        with self.storage.sessions() as session:
            require_actor(session, profile_id)
            rule = session.scalar(select(TaskReminder).where(
                TaskReminder.profile_id == profile_id, TaskReminder.task_id == task_id,
            ))
            task = session.get(Task, task_id)
            if rule is None or task is None or not can_read(
                session, profile_id, task.profile_id, task.visibility
            ):
                return None
            return ReminderRule(rule.lead_minutes, rule.timezone_id)

    def due(self, profile_id: int, now: datetime) -> tuple[DueTaskReminder, ...]:
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Reminder clock must include a time zone.")
        now_utc = now.astimezone(timezone.utc)
        with self.storage.sessions() as session:
            require_actor(session, profile_id)
            rules = session.scalars(select(TaskReminder).where(
                TaskReminder.profile_id == profile_id
            )).all()
            result = []
            for rule in rules:
                task = session.get(Task, rule.task_id)
                if task is None or task.completed or task.due_at is None or not can_read(
                    session, profile_id, task.profile_id, task.visibility
                ):
                    continue
                delivered = session.scalar(select(TaskReminderDelivery.id).where(
                    TaskReminderDelivery.reminder_id == rule.id,
                    TaskReminderDelivery.due_at == task.due_at,
                ))
                if delivered is not None:
                    continue
                occurrence = datetime.fromisoformat(task.due_at)
                local = _localize(occurrence, _zone(rule.timezone_id))
                if local is None:
                    continue
                due_at = (local.astimezone(timezone.utc) - timedelta(
                    minutes=rule.lead_minutes
                )).astimezone(local.tzinfo)
                if now_utc - MISSED_WINDOW < due_at.astimezone(timezone.utc) <= now_utc:
                    result.append(DueTaskReminder(
                        rule.id, task.id, task.title, occurrence, due_at,
                    ))
            return tuple(sorted(result, key=lambda item: (item.due_at, item.reminder_id)))

    def mark_delivered(self, profile_id: int, reminder: DueTaskReminder,
                       now: datetime) -> bool:
        if reminder not in self.due(profile_id, now):
            return False
        with self.storage.sessions.begin() as session:
            statement = insert(TaskReminderDelivery).values(
                reminder_id=reminder.reminder_id,
                due_at=reminder.occurrence_at.isoformat(timespec="minutes"),
                delivered_at=utc_now(),
            ).on_conflict_do_nothing(index_elements=["reminder_id", "due_at"])
            return session.execute(statement).rowcount == 1

    def recent_deliveries(self, profile_id: int, limit: int = 5
                          ) -> tuple[DeliveredTaskReminder, ...]:
        if not 1 <= limit <= 50:
            raise ValueError("Choose between 1 and 50 reminders.")
        with self.storage.sessions() as session:
            household_profiles = member_ids(session, profile_id)
            rows = session.execute(select(
                TaskReminderDelivery, TaskReminder, Task,
            ).join(TaskReminder, TaskReminderDelivery.reminder_id == TaskReminder.id)
                .join(Task, TaskReminder.task_id == Task.id).where(
                    TaskReminder.profile_id == profile_id,
                    or_(Task.profile_id == profile_id, and_(
                        Task.visibility == "household", Task.profile_id.in_(household_profiles),
                    )),
                ).order_by(TaskReminderDelivery.delivered_at.desc()).limit(limit)).all()
            return tuple(DeliveredTaskReminder(
                task.id, task.title, datetime.fromisoformat(delivery.delivered_at),
                rule.timezone_id,
            ) for delivery, rule, task in rows)
