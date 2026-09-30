"""Profile-scoped calorie goals and daily food logs."""

from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import func, select

from solar_forge_desktop.storage import CalorieGoal, FoodLog, Profile, Storage, utc_now


@dataclass(frozen=True)
class FoodItem:
    id: int
    food_name: str
    calories: int
    created_at: str


@dataclass(frozen=True)
class CalorieDay:
    date: date
    target: int
    has_custom_goal: bool
    consumed: int
    remaining: int
    progress_percent: int
    total_logs: int
    foods: tuple[FoodItem, ...]


def _day(value: date) -> str:
    if not isinstance(value, date) or isinstance(value, datetime):
        raise ValueError("Choose a valid date.")
    return value.isoformat()


def _integer(value: str, message: str) -> int:
    try:
        if not value.strip() or any(character not in "0123456789-" for character in value.strip()):
            raise ValueError
        return int(value.strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(message) from exc


class CalorieService:
    def __init__(self, storage: Storage):
        self.storage = storage

    def view(self, profile_id: int, selected: date, limit: int = 500) -> CalorieDay:
        day = _day(selected)
        if not 1 <= limit <= 500:
            raise ValueError("Food log limit must be between 1 and 500.")
        with self.storage.sessions() as session:
            if session.get(Profile, profile_id) is None:
                raise ValueError("Profile not found.")
            exact = session.scalar(select(CalorieGoal).where(
                CalorieGoal.profile_id == profile_id, CalorieGoal.date == day
            ))
            goal = exact
            if goal is None:
                goal = session.scalar(
                    select(CalorieGoal).where(
                        CalorieGoal.profile_id == profile_id, CalorieGoal.date < day
                    ).order_by(CalorieGoal.date.desc()).limit(1)
                )
            if goal is None:
                goal = session.scalar(
                    select(CalorieGoal).where(CalorieGoal.profile_id == profile_id)
                    .order_by(CalorieGoal.date).limit(1)
                )
            target = goal.target_calories if goal is not None else 2000
            total, consumed = session.execute(
                select(func.count(), func.coalesce(func.sum(FoodLog.calories), 0)).where(
                    FoodLog.profile_id == profile_id, FoodLog.date == day
                )
            ).one()
            rows = session.scalars(
                select(FoodLog).where(FoodLog.profile_id == profile_id, FoodLog.date == day)
                .order_by(FoodLog.created_at.desc(), FoodLog.id.desc()).limit(limit)
            ).all()
            return CalorieDay(
                selected, target, exact is not None, consumed, target - consumed,
                min(100, consumed * 100 // target), total,
                tuple(FoodItem(row.id, row.food_name, row.calories, row.created_at)
                      for row in rows),
            )

    def set_goal(self, profile_id: int, selected: date, target_raw: str) -> None:
        day = _day(selected)
        target = _integer(target_raw, "Please enter a valid integer for target calories.")
        if target <= 0:
            raise ValueError("Calorie target must be greater than zero.")
        if target > 10_000:
            raise ValueError("Calorie target must be 10,000 or fewer.")
        with self.storage.sessions.begin() as session:
            if session.get(Profile, profile_id) is None:
                raise ValueError("Profile not found.")
            goal = session.scalar(select(CalorieGoal).where(
                CalorieGoal.profile_id == profile_id, CalorieGoal.date == day
            ))
            if goal is None:
                session.add(CalorieGoal(
                    profile_id=profile_id, date=day, target_calories=target
                ))
            else:
                goal.target_calories = target

    def add_food(
        self, profile_id: int, selected: date, name: str, calories_raw: str
    ) -> int:
        day = _day(selected)
        name = name.strip()
        if not name:
            raise ValueError("Food name is required.")
        if len(name) > 100:
            raise ValueError("Food name must be 100 characters or fewer.")
        calories = _integer(calories_raw, "Please enter a valid integer for calorie count.")
        if calories < 0:
            raise ValueError("Calories cannot be negative.")
        if calories > 5000:
            raise ValueError("Calories must be 5,000 or fewer per item.")
        with self.storage.sessions.begin() as session:
            if session.get(Profile, profile_id) is None:
                raise ValueError("Profile not found.")
            food = FoodLog(
                profile_id=profile_id, food_name=name, calories=calories,
                date=day, created_at=utc_now(),
            )
            session.add(food)
            session.flush()
            return food.id

    def delete_food(self, profile_id: int, food_id: int) -> None:
        with self.storage.sessions.begin() as session:
            food = session.scalar(select(FoodLog).where(
                FoodLog.id == food_id, FoodLog.profile_id == profile_id
            ))
            if food is None:
                raise ValueError("Food log entry not found.")
            session.delete(food)
