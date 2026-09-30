"""Profile-scoped weekly dinners, reusable favorites, and grocery counts."""

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import func, select

from solar_forge_desktop.storage import FavoriteMeal, MealPlan, Profile, Storage, utc_now


@dataclass(frozen=True)
class PlannedMeal:
    id: int
    date: date
    name: str
    ingredients: str


@dataclass(frozen=True)
class FavoriteItem:
    id: int
    name: str
    ingredients: str


@dataclass(frozen=True)
class MealWeek:
    start: date
    end: date
    days: tuple[tuple[date, PlannedMeal | None], ...]
    favorites: tuple[FavoriteItem, ...]
    groceries: tuple[tuple[str, int], ...]


def _day(value: date) -> date:
    if not isinstance(value, date) or isinstance(value, datetime):
        raise ValueError("Choose a valid day.")
    return value


def _name(raw: str, error: str) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(error)
    value = raw.strip()
    if len(value) > 150:
        raise ValueError("Meal name must be 150 characters or fewer.")
    return value


def _ingredients(raw: str | None) -> str:
    if raw is None:
        return ""
    if not isinstance(raw, str):
        raise ValueError("Grocery items must be text.")
    return "\n".join(line.strip() for line in raw.splitlines() if line.strip())


def _favorite(row: FavoriteMeal) -> FavoriteItem:
    return FavoriteItem(row.id, row.name, row.ingredients)


class MealService:
    def __init__(self, storage: Storage):
        self.storage = storage

    def view(self, profile_id: int, selected: date) -> MealWeek:
        start = _day(selected) - timedelta(days=selected.weekday())
        end = start + timedelta(days=6)
        with self.storage.sessions() as session:
            if session.get(Profile, profile_id) is None:
                raise ValueError("Profile not found.")
            plans = session.scalars(select(MealPlan).where(
                MealPlan.profile_id == profile_id,
                MealPlan.meal_date.between(start.isoformat(), end.isoformat()),
            ).order_by(MealPlan.meal_date)).all()
            favorites = session.scalars(select(FavoriteMeal).where(
                FavoriteMeal.profile_id == profile_id
            ).order_by(FavoriteMeal.name, FavoriteMeal.id)).all()
            by_date = {
                row.meal_date: PlannedMeal(
                    row.id, date.fromisoformat(row.meal_date), row.meal_name, row.ingredients
                ) for row in plans
            }
            counts: Counter[str] = Counter()
            labels: dict[str, str] = {}
            for plan in plans:
                for ingredient in _ingredients(plan.ingredients).splitlines():
                    key = ingredient.casefold()
                    counts[key] += 1
                    labels.setdefault(key, ingredient)
            return MealWeek(
                start, end,
                tuple((day, by_date.get(day.isoformat()))
                      for day in (start + timedelta(days=i) for i in range(7))),
                tuple(_favorite(row) for row in favorites),
                tuple((labels[key], counts[key]) for key in sorted(counts)),
            )

    def save_plan(self, profile_id: int, selected: date, name: str = "",
                  ingredients: str | None = None, favorite_id: int | None = None,
                  save_favorite: bool = False) -> int:
        day = _day(selected).isoformat()
        with self.storage.sessions.begin() as session:
            if session.get(Profile, profile_id) is None:
                raise ValueError("Profile not found.")
            favorite = None
            if favorite_id is not None:
                favorite = session.scalar(select(FavoriteMeal).where(
                    FavoriteMeal.id == favorite_id, FavoriteMeal.profile_id == profile_id
                ))
            if favorite is not None:
                meal_name, items = favorite.name, favorite.ingredients
            else:
                meal_name = _name(name, "Enter a meal name or choose a favorite.")
                items = _ingredients(ingredients)
            plan = session.scalar(select(MealPlan).where(
                MealPlan.profile_id == profile_id, MealPlan.meal_date == day
            ))
            if plan is None:
                plan = MealPlan(profile_id=profile_id, meal_date=day,
                                meal_name=meal_name, ingredients=items, created_at=utc_now())
                session.add(plan)
            else:
                plan.meal_name, plan.ingredients = meal_name, items
            if save_favorite and session.scalar(select(FavoriteMeal.id).where(
                FavoriteMeal.profile_id == profile_id,
                func.lower(FavoriteMeal.name) == meal_name.lower(),
            )) is None:
                session.add(FavoriteMeal(profile_id=profile_id, name=meal_name,
                                         ingredients=items, created_at=utc_now()))
            session.flush()
            return plan.id

    def delete_plan(self, profile_id: int, plan_id: int) -> None:
        with self.storage.sessions.begin() as session:
            plan = session.scalar(select(MealPlan).where(
                MealPlan.id == plan_id, MealPlan.profile_id == profile_id
            ))
            if plan is None:
                raise ValueError("Meal not found.")
            session.delete(plan)

    def add_favorite(self, profile_id: int, name: str, ingredients: str | None = None) -> int:
        meal_name = _name(name, "Favorite meal name is required.")
        items = _ingredients(ingredients)
        with self.storage.sessions.begin() as session:
            if session.get(Profile, profile_id) is None:
                raise ValueError("Profile not found.")
            if session.scalar(select(FavoriteMeal.id).where(
                FavoriteMeal.profile_id == profile_id,
                func.lower(FavoriteMeal.name) == meal_name.lower(),
            )) is not None:
                raise ValueError(f"{meal_name} is already a favorite.")
            favorite = FavoriteMeal(profile_id=profile_id, name=meal_name,
                                    ingredients=items, created_at=utc_now())
            session.add(favorite)
            session.flush()
            return favorite.id

    def delete_favorite(self, profile_id: int, favorite_id: int) -> None:
        with self.storage.sessions.begin() as session:
            favorite = session.scalar(select(FavoriteMeal).where(
                FavoriteMeal.id == favorite_id, FavoriteMeal.profile_id == profile_id
            ))
            if favorite is None:
                raise ValueError("Favorite not found.")
            session.delete(favorite)
