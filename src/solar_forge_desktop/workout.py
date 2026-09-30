"""Profile-scoped daily exercise logs for the desktop workout tracker."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select

from solar_forge_desktop.storage import Profile, Storage, WorkoutLog, utc_now


@dataclass(frozen=True)
class WorkoutItem:
    id: int
    exercise_name: str
    sets: int
    reps: int
    is_bodyweight: bool
    weight_lbs: Decimal | None
    notes: str | None


@dataclass(frozen=True)
class WorkoutDay:
    date: date
    exercise_count: int
    total_sets: int
    total_reps: int
    exercises: tuple[WorkoutItem, ...]


def _validated_day(value: date) -> str:
    if not isinstance(value, date) or isinstance(value, datetime):
        raise ValueError("Choose a valid date.")
    return value.isoformat()


def _validated_entry(
    name: str, sets: int, reps: int, is_bodyweight: bool,
    weight_raw: str | None, notes: str | None,
) -> tuple[str, int, int, bool, str | None, str | None]:
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Exercise name is required.")
    name = name.strip()
    if len(name) > 150:
        raise ValueError("Exercise name must be 150 characters or fewer.")
    for label, value in (("Sets", sets), ("Reps", reps)):
        if type(value) is not int:
            raise ValueError(f"{label} must be a whole number.")
        if value < 1:
            raise ValueError(f"{label} must be at least 1.")
    if type(is_bodyweight) is not bool:
        raise ValueError("Choose a valid bodyweight setting.")
    weight = None
    if not is_bodyweight and weight_raw is not None and not isinstance(weight_raw, str):
        raise ValueError("Weight must be a valid number.")
    if not is_bodyweight and weight_raw is not None and weight_raw.strip():
        try:
            parsed = Decimal(weight_raw.strip())
        except InvalidOperation as exc:
            raise ValueError("Weight must be a valid number.") from exc
        if not parsed.is_finite():
            raise ValueError("Weight must be a valid number.")
        if parsed < 0:
            raise ValueError("Weight cannot be negative.")
        weight = str(parsed)
    if notes is not None and not isinstance(notes, str):
        raise ValueError("Notes must be text.")
    return name, sets, reps, is_bodyweight, weight, (notes or "").strip() or None


class WorkoutService:
    def __init__(self, storage: Storage):
        self.storage = storage

    def view(self, profile_id: int, selected: date, limit: int = 200) -> WorkoutDay:
        day = _validated_day(selected)
        if not 1 <= limit <= 500:
            raise ValueError("Workout history limit must be between 1 and 500.")
        with self.storage.sessions() as session:
            if session.get(Profile, profile_id) is None:
                raise ValueError("Profile not found.")
            count, sets, reps = session.execute(
                select(func.count(), func.coalesce(func.sum(WorkoutLog.sets), 0),
                       func.coalesce(func.sum(WorkoutLog.reps), 0)).where(
                    WorkoutLog.profile_id == profile_id, WorkoutLog.date == day
                )
            ).one()
            rows = session.scalars(select(WorkoutLog).where(
                WorkoutLog.profile_id == profile_id, WorkoutLog.date == day
            ).order_by(WorkoutLog.created_at.desc(), WorkoutLog.id.desc()).limit(limit)).all()
            items = tuple(WorkoutItem(
                row.id, row.exercise_name, row.sets, row.reps, row.is_bodyweight,
                Decimal(row.weight_lbs) if row.weight_lbs is not None else None,
                row.notes,
            ) for row in reversed(rows))
            return WorkoutDay(selected, count, sets, reps, items)

    def add(
        self, profile_id: int, selected: date, name: str, sets: int, reps: int,
        is_bodyweight: bool, weight_raw: str | None = None, notes: str | None = None,
    ) -> int:
        day = _validated_day(selected)
        name, sets, reps, is_bodyweight, weight, notes = _validated_entry(
            name, sets, reps, is_bodyweight, weight_raw, notes
        )
        with self.storage.sessions.begin() as session:
            if session.get(Profile, profile_id) is None:
                raise ValueError("Profile not found.")
            entry = WorkoutLog(
                profile_id=profile_id, date=day, exercise_name=name,
                sets=sets, reps=reps, is_bodyweight=is_bodyweight,
                weight_lbs=weight, notes=notes, created_at=utc_now(),
            )
            session.add(entry)
            session.flush()
            return entry.id

    def edit(
        self, profile_id: int, entry_id: int, name: str, sets: int, reps: int,
        is_bodyweight: bool, weight_raw: str | None = None, notes: str | None = None,
    ) -> None:
        name, sets, reps, is_bodyweight, weight, notes = _validated_entry(
            name, sets, reps, is_bodyweight, weight_raw, notes
        )
        with self.storage.sessions.begin() as session:
            entry = session.scalar(select(WorkoutLog).where(
                WorkoutLog.id == entry_id, WorkoutLog.profile_id == profile_id
            ))
            if entry is None:
                raise ValueError("Exercise not found.")
            entry.exercise_name = name
            entry.sets = sets
            entry.reps = reps
            entry.is_bodyweight = is_bodyweight
            entry.weight_lbs = weight
            entry.notes = notes

    def delete(self, profile_id: int, entry_id: int) -> None:
        with self.storage.sessions.begin() as session:
            entry = session.scalar(select(WorkoutLog).where(
                WorkoutLog.id == entry_id, WorkoutLog.profile_id == profile_id
            ))
            if entry is None:
                raise ValueError("Exercise not found.")
            session.delete(entry)
