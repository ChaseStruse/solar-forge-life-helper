"""Profile-scoped weight goals, daily weigh-ins, and trend calculations."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select

from solar_forge_desktop.storage import Profile, Storage, WeightGoal, WeightLog, utc_now


@dataclass(frozen=True)
class GoalItem:
    start_weight: Decimal
    start_date: date
    target_weight: Decimal
    target_date: date


@dataclass(frozen=True)
class WeighInItem:
    id: int
    date: date
    weight: Decimal
    difference: Decimal


@dataclass(frozen=True)
class WeightView:
    goal: GoalItem | None
    latest_weight: Decimal | None
    latest_date: date | None
    total_change: Decimal
    remaining: Decimal
    progress_percent: int
    is_losing: bool
    total_logs: int
    logs: tuple[WeighInItem, ...]
    chart_points: tuple[tuple[date, Decimal], ...]


def _date(value: date) -> str:
    if not isinstance(value, date) or isinstance(value, datetime):
        raise ValueError("Choose a valid date.")
    return value.isoformat()


def _weight(raw: str, invalid_message: str) -> Decimal:
    try:
        value = Decimal(raw.strip())
    except (AttributeError, InvalidOperation) as exc:
        raise ValueError(invalid_message) from exc
    if not value.is_finite():
        raise ValueError(invalid_message)
    return value


class WeightService:
    def __init__(self, storage: Storage):
        self.storage = storage

    def view(self, profile_id: int, limit: int = 200) -> WeightView:
        if not 1 <= limit <= 500:
            raise ValueError("Weight history limit must be between 1 and 500.")
        with self.storage.sessions() as session:
            if session.get(Profile, profile_id) is None:
                raise ValueError("Profile not found.")
            stored_goal = session.scalar(select(WeightGoal).where(
                WeightGoal.profile_id == profile_id
            ))
            goal = GoalItem(
                Decimal(stored_goal.start_weight), date.fromisoformat(stored_goal.start_date),
                Decimal(stored_goal.target_weight), date.fromisoformat(stored_goal.target_date),
            ) if stored_goal is not None else None
            total_logs = session.scalar(select(func.count()).select_from(WeightLog).where(
                WeightLog.profile_id == profile_id
            ))
            rows = session.scalars(
                select(WeightLog).where(WeightLog.profile_id == profile_id)
                .order_by(WeightLog.date.desc(), WeightLog.id.desc()).limit(limit + 1)
            ).all()
            visible = rows[:limit]
            latest_weight = Decimal(rows[0].weight) if rows else (
                goal.start_weight if goal else None
            )
            latest_date = date.fromisoformat(rows[0].date) if rows else (
                goal.start_date if goal else None
            )
            logs = []
            for index, row in enumerate(visible):
                previous = Decimal(rows[index + 1].weight) if index + 1 < len(rows) else (
                    goal.start_weight if goal else Decimal(0)
                )
                difference = Decimal(row.weight) - previous if (
                    index + 1 < len(rows) or goal
                ) else Decimal(0)
                logs.append(WeighInItem(
                    row.id, date.fromisoformat(row.date), Decimal(row.weight), difference
                ))
            chart = [(item.date, item.weight) for item in reversed(logs)]
            if goal and not any(day == goal.start_date for day, _ in chart):
                chart.insert(0, (goal.start_date, goal.start_weight))
            change = (latest_weight - goal.start_weight) if goal else Decimal(0)
            remaining = abs(latest_weight - goal.target_weight) if goal else Decimal(0)
            is_losing = goal.start_weight >= goal.target_weight if goal else True
            progress = 0
            if goal:
                total_goal = abs(goal.start_weight - goal.target_weight)
                if total_goal:
                    actual = -change if is_losing else change
                    progress = min(100, max(0, int(actual / total_goal * 100)))
            return WeightView(
                goal, latest_weight, latest_date, change, remaining, progress,
                is_losing, total_logs, tuple(logs), tuple(chart),
            )

    def set_goal(
        self, profile_id: int, start_raw: str, start_date: date,
        target_raw: str, target_date: date,
    ) -> None:
        invalid = "Please enter valid numbers for weights and select valid dates."
        start = _weight(start_raw, invalid)
        target = _weight(target_raw, invalid)
        start_day = _date(start_date)
        target_day = _date(target_date)
        if start <= 0 or target <= 0:
            raise ValueError("Weight parameters must be greater than zero.")
        if start_date >= target_date:
            raise ValueError("Target date must be after the starting date.")
        with self.storage.sessions.begin() as session:
            if session.get(Profile, profile_id) is None:
                raise ValueError("Profile not found.")
            goal = session.scalar(select(WeightGoal).where(
                WeightGoal.profile_id == profile_id
            ))
            if goal is None:
                session.add(WeightGoal(
                    profile_id=profile_id, start_weight=str(start), start_date=start_day,
                    target_weight=str(target), target_date=target_day,
                ))
            else:
                goal.start_weight = str(start)
                goal.start_date = start_day
                goal.target_weight = str(target)
                goal.target_date = target_day

    def log(self, profile_id: int, selected: date, raw: str) -> tuple[int, bool]:
        day = _date(selected)
        weight = _weight(raw, "Please enter a valid weight and select a valid date.")
        if weight <= 0:
            raise ValueError("Weigh-in weight must be greater than zero.")
        with self.storage.sessions.begin() as session:
            if session.get(Profile, profile_id) is None:
                raise ValueError("Profile not found.")
            entry = session.scalar(select(WeightLog).where(
                WeightLog.profile_id == profile_id, WeightLog.date == day
            ))
            updated = entry is not None
            if entry is None:
                entry = WeightLog(
                    profile_id=profile_id, weight=str(weight), date=day,
                    created_at=utc_now(),
                )
                session.add(entry)
            else:
                entry.weight = str(weight)
            session.flush()
            return entry.id, updated

    def delete(self, profile_id: int, log_id: int) -> None:
        with self.storage.sessions.begin() as session:
            entry = session.scalar(select(WeightLog).where(
                WeightLog.id == log_id, WeightLog.profile_id == profile_id
            ))
            if entry is None:
                raise ValueError("Weigh-in entry not found.")
            session.delete(entry)
