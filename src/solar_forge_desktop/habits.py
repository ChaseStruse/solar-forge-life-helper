"""Profile-scoped weekly yes/no habit tracking."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import func, select

from solar_forge_desktop.storage import Habit, HabitCheck, Profile, Storage, utc_now


@dataclass(frozen=True)
class HabitItem:
    id: int
    name: str


@dataclass(frozen=True)
class HabitWeek:
    start: date
    days: tuple[date, ...]
    habits: tuple[HabitItem, ...]
    checked: frozenset[tuple[int, date]]
    completed_count: int
    completion_percent: int


def week_start(selected: date) -> date:
    return selected - timedelta(days=selected.weekday())


class HabitService:
    def __init__(self, storage: Storage):
        self.storage = storage

    def view(self, profile_id: int, selected: date) -> HabitWeek:
        start = week_start(selected)
        end = start + timedelta(days=6)
        with self.storage.sessions() as session:
            if session.get(Profile, profile_id) is None:
                raise ValueError("Profile not found.")
            habits = session.scalars(
                select(Habit).where(Habit.profile_id == profile_id)
                .order_by(Habit.created_at, Habit.id)
            ).all()
            checks = session.execute(
                select(HabitCheck.habit_id, HabitCheck.check_date)
                .join(Habit)
                .where(Habit.profile_id == profile_id,
                       HabitCheck.check_date.between(start.isoformat(), end.isoformat()))
            ).all()
            checked = frozenset((habit_id, date.fromisoformat(day)) for habit_id, day in checks)
            count = len(checked)
            possible = len(habits) * 7
            return HabitWeek(
                start, tuple(start + timedelta(days=offset) for offset in range(7)),
                tuple(HabitItem(habit.id, habit.name) for habit in habits),
                checked, count, round(count / possible * 100) if possible else 0,
            )

    def add(self, profile_id: int, name: str) -> int:
        name = name.strip()
        if not name:
            raise ValueError("Habit name is required.")
        if len(name) > 100:
            raise ValueError("Habit name must be 100 characters or fewer.")
        with self.storage.sessions.begin() as session:
            if session.get(Profile, profile_id) is None:
                raise ValueError("Profile not found.")
            duplicate = session.scalar(
                select(Habit.id).where(
                    Habit.profile_id == profile_id, func.lower(Habit.name) == name.lower()
                ).limit(1)
            )
            if duplicate is not None:
                raise ValueError(f"{name} is already being tracked.")
            habit = Habit(profile_id=profile_id, name=name, created_at=utc_now())
            session.add(habit)
            session.flush()
            return habit.id

    def toggle(self, profile_id: int, habit_id: int, day: date) -> None:
        if not isinstance(day, date) or isinstance(day, datetime):
            raise ValueError("Choose a valid day.")
        with self.storage.sessions.begin() as session:
            habit = session.scalar(select(Habit).where(
                Habit.id == habit_id, Habit.profile_id == profile_id
            ))
            if habit is None:
                raise ValueError("Habit not found.")
            existing = session.scalar(select(HabitCheck).where(
                HabitCheck.habit_id == habit_id,
                HabitCheck.check_date == day.isoformat(),
            ))
            if existing is None:
                session.add(HabitCheck(
                    habit_id=habit_id, check_date=day.isoformat(), created_at=utc_now()
                ))
            else:
                session.delete(existing)

    def delete(self, profile_id: int, habit_id: int) -> None:
        with self.storage.sessions.begin() as session:
            habit = session.scalar(select(Habit).where(
                Habit.id == habit_id, Habit.profile_id == profile_id
            ))
            if habit is None:
                raise ValueError("Habit not found.")
            session.delete(habit)
