"""Isolated desktop SQLite storage. Legacy web databases are never upgraded in place."""

import os
import sqlite3
import tempfile
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    event,
    select,
    text,
)
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker


class Base(DeclarativeBase):
    pass


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    username: Mapped[str | None] = mapped_column(String(80), unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(200))
    tasks: Mapped[list["Task"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    journal_entries: Mapped[list["JournalEntry"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    medicine_logs: Mapped[list["MedicineLog"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    habits: Mapped[list["Habit"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    calorie_goals: Mapped[list["CalorieGoal"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    food_logs: Mapped[list["FoodLog"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    weight_goals: Mapped[list["WeightGoal"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    weight_logs: Mapped[list["WeightLog"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    workout_logs: Mapped[list["WorkoutLog"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    pets: Mapped[list["Pet"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    meal_plans: Mapped[list["MealPlan"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    favorite_meals: Mapped[list["FavoriteMeal"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    maintenance_items: Mapped[list["MaintenanceItem"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    calendar_events: Mapped[list["CalendarEvent"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    settings: Mapped["ProfileSettings | None"] = relationship(
        back_populates="profile", cascade="all, delete-orphan", uselist=False
    )


class ProfileSettings(Base):
    __tablename__ = "profile_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    bio: Mapped[str] = mapped_column(Text, nullable=False, default="Solar Forge Life Helper member")
    avatar_color: Mapped[str] = mapped_column(String(20), nullable=False, default="#8b5cf6")
    avatar_emoji: Mapped[str] = mapped_column(String(10), nullable=False, default="🌙")
    favorite_apps: Mapped[str] = mapped_column(
        String(255), nullable=False, default="budget,calorie,weight,journal"
    )
    visible_widgets: Mapped[str] = mapped_column(
        String(255), nullable=False, default="journal,weight,calorie"
    )
    highlight_order: Mapped[str] = mapped_column(
        String(255), nullable=False, default="budget,calorie,weight,journal"
    )
    quick_access_apps: Mapped[str] = mapped_column(
        String(255), nullable=False,
        default="budget,calorie,weight,journal,workout,tasks,calendar,habits,medicine,pets,"
                "maintenance,meals",
    )
    profile: Mapped[Profile] = relationship(back_populates="settings")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)
    completed_at: Mapped[str | None] = mapped_column(String(40))
    profile: Mapped[Profile] = relationship(back_populates="tasks")


class MonthlyIncome(Base):
    __tablename__ = "monthly_incomes"
    __table_args__ = (UniqueConstraint("profile_id", "month_year"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    month_year: Mapped[str] = mapped_column(String(7), nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    due_date: Mapped[str | None] = mapped_column(String(10))
    month_year: Mapped[str] = mapped_column(String(7), nullable=False)
    tag: Mapped[str | None] = mapped_column(String(50))
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("expenses.id", ondelete="CASCADE")
    )
    recurrence: Mapped[str] = mapped_column(String(20), nullable=False, default="none")


class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    updated_at: Mapped[str] = mapped_column(String(40), nullable=False)
    profile: Mapped[Profile] = relationship(back_populates="journal_entries")


class MedicineLog(Base):
    __tablename__ = "medicine_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    recipient: Mapped[str] = mapped_column(String(100), nullable=False)
    medicine_name: Mapped[str] = mapped_column(String(150), nullable=False)
    dosage: Mapped[str] = mapped_column(String(100), nullable=False)
    given_at: Mapped[str] = mapped_column(String(16), nullable=False)
    next_due_at: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)
    profile: Mapped[Profile] = relationship(back_populates="medicine_logs")


class Habit(Base):
    __tablename__ = "habits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)
    profile: Mapped[Profile] = relationship(back_populates="habits")
    checks: Mapped[list["HabitCheck"]] = relationship(
        back_populates="habit", cascade="all, delete-orphan"
    )


class HabitCheck(Base):
    __tablename__ = "habit_checks"
    __table_args__ = (UniqueConstraint("habit_id", "check_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    habit_id: Mapped[int] = mapped_column(
        ForeignKey("habits.id", ondelete="CASCADE"), nullable=False, index=True
    )
    check_date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)
    habit: Mapped[Habit] = relationship(back_populates="checks")


class CalorieGoal(Base):
    __tablename__ = "calorie_goals"
    __table_args__ = (UniqueConstraint("profile_id", "date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date: Mapped[str] = mapped_column(String(10), nullable=False)
    target_calories: Mapped[int] = mapped_column(Integer, nullable=False)
    profile: Mapped[Profile] = relationship(back_populates="calorie_goals")


class FoodLog(Base):
    __tablename__ = "food_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    food_name: Mapped[str] = mapped_column(String(100), nullable=False)
    calories: Mapped[int] = mapped_column(Integer, nullable=False)
    date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    profile: Mapped[Profile] = relationship(back_populates="food_logs")


class WeightGoal(Base):
    __tablename__ = "weight_goals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    start_weight: Mapped[str] = mapped_column(String(40), nullable=False)
    start_date: Mapped[str] = mapped_column(String(10), nullable=False)
    target_weight: Mapped[str] = mapped_column(String(40), nullable=False)
    target_date: Mapped[str] = mapped_column(String(10), nullable=False)
    profile: Mapped[Profile] = relationship(back_populates="weight_goals")


class WeightLog(Base):
    __tablename__ = "weight_logs"
    __table_args__ = (UniqueConstraint("profile_id", "date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    weight: Mapped[str] = mapped_column(String(40), nullable=False)
    date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)
    profile: Mapped[Profile] = relationship(back_populates="weight_logs")


class WorkoutLog(Base):
    __tablename__ = "workout_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    exercise_name: Mapped[str] = mapped_column(String(150), nullable=False)
    sets: Mapped[int] = mapped_column(Integer, nullable=False)
    reps: Mapped[int] = mapped_column(Integer, nullable=False)
    is_bodyweight: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    weight_lbs: Mapped[str | None] = mapped_column(String(40))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    profile: Mapped[Profile] = relationship(back_populates="workout_logs")


class Pet(Base):
    __tablename__ = "pets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    animal_type: Mapped[str] = mapped_column(String(60), nullable=False)
    breed: Mapped[str | None] = mapped_column(String(100))
    birth_date: Mapped[str | None] = mapped_column(String(10))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    profile: Mapped[Profile] = relationship(back_populates="pets")
    care_records: Mapped[list["PetCareRecord"]] = relationship(
        back_populates="pet", cascade="all, delete-orphan"
    )


class PetCareRecord(Base):
    __tablename__ = "pet_care_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pet_id: Mapped[int] = mapped_column(
        ForeignKey("pets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    record_date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    details: Mapped[str] = mapped_column(Text, nullable=False)
    weight: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    pet: Mapped[Pet] = relationship(back_populates="care_records")


class MealPlan(Base):
    __tablename__ = "meal_plans"
    __table_args__ = (UniqueConstraint("profile_id", "meal_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    meal_date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    meal_name: Mapped[str] = mapped_column(String(150), nullable=False)
    ingredients: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)
    profile: Mapped[Profile] = relationship(back_populates="meal_plans")


class FavoriteMeal(Base):
    __tablename__ = "favorite_meals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    ingredients: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    profile: Mapped[Profile] = relationship(back_populates="favorite_meals")


class MaintenanceItem(Base):
    __tablename__ = "maintenance_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    next_due_date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    recurrence_interval: Mapped[int] = mapped_column(Integer, nullable=False)
    recurrence_unit: Mapped[str] = mapped_column(String(20), nullable=False)
    estimated_cost: Mapped[str | None] = mapped_column(String(40))
    notes: Mapped[str | None] = mapped_column(Text)
    last_completed_date: Mapped[str | None] = mapped_column(String(10))
    created_at: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    profile: Mapped[Profile] = relationship(back_populates="maintenance_items")


class CalendarEvent(Base):
    __tablename__ = "calendar_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    starts_at: Mapped[str] = mapped_column(String(19), nullable=False, index=True)
    ends_at: Mapped[str] = mapped_column(String(19), nullable=False)
    all_day: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    recurrence: Mapped[str] = mapped_column(String(10), nullable=False, default="none")
    recurrence_until: Mapped[str | None] = mapped_column(String(10))
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)
    profile: Mapped[Profile] = relationship(back_populates="calendar_events")


@dataclass(frozen=True)
class TaskItem:
    id: int
    title: str
    completed: bool
    created_at: str
    completed_at: str | None


@dataclass(frozen=True)
class JournalItem:
    id: int
    title: str
    content: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class MedicineItem:
    id: int
    recipient: str
    medicine_name: str
    dosage: str
    given_at: str
    next_due_at: str
    created_at: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Storage:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(
            URL.create("sqlite+pysqlite", database=str(path)), connect_args={"timeout": 5}
        )
        event.listen(self.engine, "connect", self._configure_connection)
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)
        try:
            self._initialize()
        except BaseException:
            self.engine.dispose()
            raise

    @staticmethod
    def _configure_connection(connection, _record) -> None:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=5000")

    def _initialize(self) -> None:
        with self.engine.begin() as connection:
            version = connection.exec_driver_sql("PRAGMA user_version").scalar_one()
            if version == 0:
                tables = (
                    connection.execute(
                        text(
                            "SELECT name FROM sqlite_master WHERE type='table' "
                            "AND name NOT LIKE 'sqlite_%'"
                        )
                    )
                    .scalars()
                    .all()
                )
                if tables:
                    raise RuntimeError(
                        "This is not a new Solar Forge Python desktop database. "
                        "Choose an empty data directory."
                    )
                Base.metadata.create_all(connection)
                connection.exec_driver_sql("PRAGMA user_version=14")
            elif version not in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14):
                raise RuntimeError(f"Unsupported desktop database version: {version}")
            else:
                names = set(
                    connection.execute(
                        text("SELECT name FROM sqlite_master WHERE type='table'")
                    ).scalars()
                )
                if not {"profiles", "tasks"}.issubset(names):
                    raise RuntimeError("Desktop database is missing required tables.")
        if version == 1:
            self._upgrade_v1()
            version = 2
        with self.engine.connect() as connection:
            columns = {row[1] for row in connection.exec_driver_sql("PRAGMA table_info(profiles)")}
            if not {"username", "password_hash"}.issubset(columns):
                raise RuntimeError("Desktop database is missing account fields.")
        if version == 2:
            self._upgrade_v2()
            version = 3
        with self.engine.connect() as connection:
            tables_sql = "SELECT name FROM sqlite_master WHERE type='table'"
            tables = set(
                connection.execute(text(tables_sql)).scalars()
            )
            if not {"monthly_incomes", "expenses"}.issubset(tables):
                raise RuntimeError("Desktop database is missing budget tables.")
        if version == 3:
            self._upgrade_v3()
            version = 4
        with self.engine.connect() as connection:
            tables = set(connection.execute(text(tables_sql)).scalars())
            if "journal_entries" not in tables:
                raise RuntimeError("Desktop database is missing journal tables.")
        if version == 4:
            self._upgrade_v4()
            version = 5
        with self.engine.connect() as connection:
            tables = set(connection.execute(text(tables_sql)).scalars())
            if "medicine_logs" not in tables:
                raise RuntimeError("Desktop database is missing medicine tables.")
        if version == 5:
            self._upgrade_v5()
            version = 6
        with self.engine.connect() as connection:
            tables = set(connection.execute(text(tables_sql)).scalars())
            if not {"habits", "habit_checks"}.issubset(tables):
                raise RuntimeError("Desktop database is missing habit tables.")
        if version == 6:
            self._upgrade_v6()
            version = 7
        with self.engine.connect() as connection:
            tables = set(connection.execute(text(tables_sql)).scalars())
            if not {"calorie_goals", "food_logs"}.issubset(tables):
                raise RuntimeError("Desktop database is missing calorie tables.")
        if version == 7:
            self._upgrade_v7()
            version = 8
        with self.engine.connect() as connection:
            tables = set(connection.execute(text(tables_sql)).scalars())
            if not {"weight_goals", "weight_logs"}.issubset(tables):
                raise RuntimeError("Desktop database is missing weight tables.")
        if version == 8:
            self._upgrade_v8()
            version = 9
        with self.engine.connect() as connection:
            tables = set(connection.execute(text(tables_sql)).scalars())
            if "workout_logs" not in tables:
                raise RuntimeError("Desktop database is missing workout tables.")
        if version == 9:
            self._upgrade_v9()
            version = 10
        with self.engine.connect() as connection:
            tables = set(connection.execute(text(tables_sql)).scalars())
            if not {"pets", "pet_care_records"}.issubset(tables):
                raise RuntimeError("Desktop database is missing pet tables.")
        if version == 10:
            self._upgrade_v10()
            version = 11
        with self.engine.connect() as connection:
            tables = set(connection.execute(text(tables_sql)).scalars())
            if not {"meal_plans", "favorite_meals"}.issubset(tables):
                raise RuntimeError("Desktop database is missing meal tables.")
        if version == 11:
            self._upgrade_v11()
            version = 12
        with self.engine.connect() as connection:
            tables = set(connection.execute(text(tables_sql)).scalars())
            if "maintenance_items" not in tables:
                raise RuntimeError("Desktop database is missing maintenance tables.")
        if version == 12:
            self._upgrade_v12()
            version = 13
        with self.engine.connect() as connection:
            tables = set(connection.execute(text(tables_sql)).scalars())
            if "calendar_events" not in tables:
                raise RuntimeError("Desktop database is missing calendar tables.")
        if version == 13:
            self._upgrade_v13()
        with self.engine.connect() as connection:
            tables = set(connection.execute(text(tables_sql)).scalars())
            if "profile_settings" not in tables:
                raise RuntimeError("Desktop database is missing profile settings.")
        with self.sessions.begin() as session:
            if session.scalar(select(Profile.id).limit(1)) is None:
                session.add(Profile(name="Home"))

    def _upgrade_v1(self) -> None:
        """Keep a complete SQLite snapshot before changing an existing profile database."""
        self._snapshot_before_upgrade("pre-auth-v1")
        with self.engine.begin() as connection:
            if connection.exec_driver_sql("PRAGMA user_version").scalar_one() != 1:
                return
            connection.exec_driver_sql("ALTER TABLE profiles ADD COLUMN username VARCHAR(80)")
            connection.exec_driver_sql("ALTER TABLE profiles ADD COLUMN password_hash VARCHAR(200)")
            connection.exec_driver_sql(
                "CREATE UNIQUE INDEX ix_profiles_username ON profiles (username)"
            )
            connection.exec_driver_sql("PRAGMA user_version=2")

    def _upgrade_v2(self) -> None:
        """Add exact-cent budget tables after preserving the authenticated database."""
        self._snapshot_before_upgrade("pre-budget-v2")
        with self.engine.begin() as connection:
            if connection.exec_driver_sql("PRAGMA user_version").scalar_one() != 2:
                return
            MonthlyIncome.__table__.create(connection)
            Expense.__table__.create(connection)
            connection.exec_driver_sql("PRAGMA user_version=3")

    def _upgrade_v3(self) -> None:
        """Add private journal entries after a consistent database snapshot."""
        self._snapshot_before_upgrade("pre-journal-v3")
        with self.engine.begin() as connection:
            if connection.exec_driver_sql("PRAGMA user_version").scalar_one() != 3:
                return
            JournalEntry.__table__.create(connection)
            connection.exec_driver_sql("PRAGMA user_version=4")

    def _upgrade_v4(self) -> None:
        """Add dose logs after preserving the previous desktop database."""
        self._snapshot_before_upgrade("pre-medicine-v4")
        with self.engine.begin() as connection:
            if connection.exec_driver_sql("PRAGMA user_version").scalar_one() != 4:
                return
            MedicineLog.__table__.create(connection)
            connection.exec_driver_sql("PRAGMA user_version=5")

    def _upgrade_v5(self) -> None:
        """Add habits and daily checks after a consistent database snapshot."""
        self._snapshot_before_upgrade("pre-habits-v5")
        with self.engine.begin() as connection:
            if connection.exec_driver_sql("PRAGMA user_version").scalar_one() != 5:
                return
            Habit.__table__.create(connection)
            HabitCheck.__table__.create(connection)
            connection.exec_driver_sql("PRAGMA user_version=6")

    def _upgrade_v6(self) -> None:
        """Add daily goals and food logs after a consistent database snapshot."""
        self._snapshot_before_upgrade("pre-calorie-v6")
        with self.engine.begin() as connection:
            if connection.exec_driver_sql("PRAGMA user_version").scalar_one() != 6:
                return
            CalorieGoal.__table__.create(connection)
            FoodLog.__table__.create(connection)
            connection.exec_driver_sql("PRAGMA user_version=7")

    def _upgrade_v7(self) -> None:
        """Add weight goals and weigh-ins after a consistent database snapshot."""
        self._snapshot_before_upgrade("pre-weight-v7")
        with self.engine.begin() as connection:
            if connection.exec_driver_sql("PRAGMA user_version").scalar_one() != 7:
                return
            WeightGoal.__table__.create(connection)
            WeightLog.__table__.create(connection)
            connection.exec_driver_sql("PRAGMA user_version=8")

    def _upgrade_v8(self) -> None:
        """Add workout logs after a consistent database snapshot."""
        self._snapshot_before_upgrade("pre-workout-v8")
        with self.engine.begin() as connection:
            if connection.exec_driver_sql("PRAGMA user_version").scalar_one() != 8:
                return
            WorkoutLog.__table__.create(connection)
            connection.exec_driver_sql("PRAGMA user_version=9")

    def _upgrade_v9(self) -> None:
        """Add pet profiles and care records after a consistent database snapshot."""
        self._snapshot_before_upgrade("pre-pets-v9")
        with self.engine.begin() as connection:
            if connection.exec_driver_sql("PRAGMA user_version").scalar_one() != 9:
                return
            Pet.__table__.create(connection)
            PetCareRecord.__table__.create(connection)
            connection.exec_driver_sql("PRAGMA user_version=10")

    def _upgrade_v10(self) -> None:
        """Add meal plans and favorites after a consistent database snapshot."""
        self._snapshot_before_upgrade("pre-meals-v10")
        with self.engine.begin() as connection:
            if connection.exec_driver_sql("PRAGMA user_version").scalar_one() != 10:
                return
            MealPlan.__table__.create(connection)
            FavoriteMeal.__table__.create(connection)
            connection.exec_driver_sql("PRAGMA user_version=11")

    def _upgrade_v11(self) -> None:
        """Add maintenance items after a consistent database snapshot."""
        self._snapshot_before_upgrade("pre-maintenance-v11")
        with self.engine.begin() as connection:
            if connection.exec_driver_sql("PRAGMA user_version").scalar_one() != 11:
                return
            MaintenanceItem.__table__.create(connection)
            connection.exec_driver_sql("PRAGMA user_version=12")

    def _upgrade_v12(self) -> None:
        """Add calendar events after a consistent database snapshot."""
        self._snapshot_before_upgrade("pre-calendar-v12")
        with self.engine.begin() as connection:
            if connection.exec_driver_sql("PRAGMA user_version").scalar_one() != 12:
                return
            CalendarEvent.__table__.create(connection)
            connection.exec_driver_sql("PRAGMA user_version=13")

    def _upgrade_v13(self) -> None:
        """Add profile presentation preferences after a consistent snapshot."""
        self._snapshot_before_upgrade("pre-profile-v13")
        with self.engine.begin() as connection:
            if connection.exec_driver_sql("PRAGMA user_version").scalar_one() != 13:
                return
            ProfileSettings.__table__.create(connection)
            connection.exec_driver_sql("PRAGMA user_version=14")

    def _snapshot_before_upgrade(self, label: str) -> None:
        snapshot_path = self.path.with_name(self.path.name + "." + label)
        if not snapshot_path.exists():
            temporary_path = snapshot_path.with_name(snapshot_path.name + ".tmp")
            try:
                with closing(sqlite3.connect(self.path)) as source, closing(
                    sqlite3.connect(temporary_path)
                ) as snapshot:
                    source.backup(snapshot)
                    if snapshot.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                        raise RuntimeError("Desktop database snapshot failed its integrity check.")
                os.replace(temporary_path, snapshot_path)
            finally:
                temporary_path.unlink(missing_ok=True)

    def default_profile_id(self) -> int:
        with self.sessions() as session:
            profile_id = session.scalar(select(Profile.id).order_by(Profile.id).limit(1))
            if profile_id is None:
                raise RuntimeError("No local profile exists.")
            return profile_id

    def profile_name(self, profile_id: int) -> str:
        with self.sessions() as session:
            profile = session.get(Profile, profile_id)
            if profile is None:
                raise ValueError("Profile not found.")
            return profile.name

    def create_profile(self, name: str) -> int:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Profile name is required.")
        with self.sessions.begin() as session:
            profile = Profile(name=clean_name)
            session.add(profile)
            session.flush()
            return profile.id

    def close(self) -> None:
        self.engine.dispose()


def seed_database_from_legacy(source_path: Path, destination_path: Path) -> bool:
    """Snapshot the old Python desktop database into an empty Docker volume."""
    source_path = source_path.resolve()
    destination_path = destination_path.resolve()
    if destination_path.exists() or not source_path.is_file():
        return False
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{destination_path.name}.", suffix=".importing", dir=destination_path.parent
    )
    os.close(fd)
    temporary_path = Path(temporary_name)
    source_uri = f"file:{quote(str(source_path))}?mode=ro"
    try:
        with closing(sqlite3.connect(source_uri, uri=True)) as source, closing(
            sqlite3.connect(temporary_path)
        ) as snapshot:
            version = source.execute("PRAGMA user_version").fetchone()[0]
            tables = {
                row[0]
                for row in source.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            if (version not in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14)
                    or not {"profiles", "tasks"}.issubset(tables)):
                raise RuntimeError("The previous desktop database has an unsupported schema.")
            source.backup(snapshot)
            integrity = snapshot.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                raise RuntimeError("The previous desktop database failed its integrity check.")
            snapshot.commit()
        os.replace(temporary_path, destination_path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise
    return True
