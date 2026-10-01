"""Budget persistence and parity rules against disposable SQLite files."""

import csv
import sqlite3
from contextlib import closing
from io import StringIO
from pathlib import Path

import pytest

from solar_forge_desktop.budget import (
    BudgetService,
    current_month,
    format_money,
    money_cents,
    month_bounds,
)
from solar_forge_desktop.storage import Storage


def test_income_carry_over_and_account_isolation(tmp_path: Path) -> None:
    path = tmp_path / "budget.db"
    storage = Storage(path)
    alex = storage.default_profile_id()
    other = storage.create_profile("Other")
    budget = BudgetService(storage)
    budget.set_income(alex, "2026-07", "5250.75")
    assert budget.view(alex, "2026-07").income_cents == 525075
    assert budget.view(alex, "2026-08").income_cents == 525075
    assert budget.view(other, "2026-08").income_cents == 0
    budget.set_income(alex, "2026-08", "6000.00")
    assert budget.view(alex, "2026-08").income_cents == 600000
    storage.close()
    reopened = Storage(path)
    assert BudgetService(reopened).view(alex, "2026-08").income_cents == 600000
    reopened.close()


def test_expense_validation_and_exact_money(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "budget.db")
    profile = storage.default_profile_id()
    budget = BudgetService(storage)
    assert money_cents("0.01", income=False) == 1
    assert format_money(123456) == "$1,234.56"
    assert len(current_month()) == 7
    assert month_bounds("2028-02")[1].day == 29
    for month in ("2026-13", "2026-7", "bad"):
        with pytest.raises(ValueError, match="Month must"):
            budget.view(profile, month)
    for raw, message in (("-1", "cannot be negative"), ("bad", "Invalid income")):
        with pytest.raises(ValueError, match=message):
            budget.set_income(profile, "2026-07", raw)
    with pytest.raises(ValueError, match="Invalid income"):
        budget.set_income(profile, "2026-07", "NaN")
    with pytest.raises(ValueError, match="too large"):
        budget.set_income(profile, "2026-07", "100000000.00")
    for name, amount, due, tag, message in (
        (" ", "10", "", "", "name is required"),
        ("Rent", "0", "", "", "greater than zero"),
        ("Rent", "oops", "", "", "Invalid expense"),
        ("Rent", "10", "2026-08-01", "", "active budget month"),
        ("Rent", "10", "July 15", "", "YYYY-MM-DD"),
        ("Rent", "10", "2026-07-99", "", "YYYY-MM-DD"),
        ("Rent", "10", "", "x" * 51, "50 characters"),
    ):
        with pytest.raises(ValueError, match=message):
            budget.add_expense(profile, "2026-07", name, amount, due, tag)
    first = budget.add_expense(profile, "2026-07", " Rent ", "1200.25", tag="House")
    invalid_repeat = budget.add_expense(
        profile, "2026-07", "One off", "1", "2026-07-11", recurrence="yearly"
    )
    saved = next(item for item in budget.view(profile, "2026-07").expenses if item.id == first)
    assert (saved.name, saved.amount_cents, saved.recurrence) == ("Rent", 120025, "none")
    invalid_row = next(
        item for item in budget.view(profile, "2026-07").expenses if item.id == invalid_repeat
    )
    assert invalid_row.recurrence == "none"
    with pytest.raises(ValueError, match="Profile not found"):
        budget.set_income(999, "2026-07", "10")
    with pytest.raises(ValueError, match="Profile not found"):
        budget.add_expense(999, "2026-07", "Bad", "10")
    with pytest.raises(ValueError, match="Profile not found"):
        budget.view(999, "2026-07")
    storage.close()


def test_recurring_projection_and_parent_cascade(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "budget.db")
    profile = storage.default_profile_id()
    budget = BudgetService(storage)
    weekly = budget.add_expense(
        profile, "2026-07", "Cleaning", "50", "2026-07-10", "House", "weekly"
    )
    july = budget.view(profile, "2026-07")
    assert [r.due_date for r in july.expenses] == [
        "2026-07-10", "2026-07-17", "2026-07-24", "2026-07-31"
    ]
    assert july.total_expenses_cents == 20000
    assert all(r.tag == "House" for r in july.expenses)
    august = budget.view(profile, "2026-08")
    assert len(august.expenses) == 4
    assert len(budget.view(profile, "2026-08").expenses) == 4
    assert all(r.parent_id == weekly for r in august.expenses)
    budget.delete_expense(profile, weekly)
    assert budget.view(profile, "2026-07").expenses == ()
    assert budget.view(profile, "2026-08").expenses == ()
    storage.close()


def test_monthly_clamping_biweekly_and_no_due_date(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "budget.db")
    profile = storage.default_profile_id()
    budget = BudgetService(storage)
    budget.add_expense(profile, "2026-01", "Rent", "100", "2026-01-31", recurrence="monthly")
    assert budget.view(profile, "2026-02").expenses[0].due_date == "2026-02-28"
    assert budget.view(profile, "2028-02").expenses[0].due_date == "2028-02-29"
    budget.add_expense(profile, "2026-07", "Biweekly", "10", "2026-07-03", recurrence="biweekly")
    july = [r for r in budget.view(profile, "2026-07").expenses if r.name == "Biweekly"]
    assert [r.due_date for r in july] == ["2026-07-03", "2026-07-17", "2026-07-31"]
    august_biweekly = [
        r.due_date for r in budget.view(profile, "2026-08").expenses if r.name == "Biweekly"
    ]
    assert august_biweekly == [
        "2026-08-14", "2026-08-28"
    ]
    no_date = budget.add_expense(profile, "2026-07", "No date", "5", recurrence="weekly")
    no_date_row = next(r for r in budget.view(profile, "2026-07").expenses if r.id == no_date)
    assert no_date_row.recurrence == "none"
    storage.close()


def test_filter_sort_csv_edit_and_ownership(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "budget.db")
    first = storage.default_profile_id()
    other = storage.create_profile("Other")
    budget = BudgetService(storage)
    budget.set_income(first, "2026-07", "100")
    injected = budget.add_expense(first, "2026-07", "=Invoice", "12.50", "2026-07-03", "House")
    budget.add_expense(first, "2026-07", "Alpha", "10.00", "2026-07-01", "Car")
    budget.add_expense(first, "2026-07", "No date", "5.00")
    view = budget.view(first, "2026-07", tag="House")
    assert [row.name for row in view.expenses] == ["=Invoice"]
    assert (view.income_cents, view.total_expenses_cents, view.savings_cents) == (10000, 2750, 7250)
    assert view.tags == ("Car", "House", "Subscriptions")
    assert [r.name for r in budget.view(first, "2026-07", sort_by="name").expenses] == [
        "=Invoice", "Alpha", "No date"
    ]
    amount_sorted = budget.view(first, "2026-07", sort_by="amount", direction="desc")
    assert [r.name for r in amount_sorted.expenses] == [
        "=Invoice", "Alpha", "No date"
    ]
    rows = list(csv.DictReader(StringIO(budget.export_csv(first, "2026-07", tag="House"))))
    assert rows[0]["Expense"] == "'=Invoice"
    assert rows[0]["Amount"] == "12.50"
    assert len(rows) == 1
    with pytest.raises(ValueError, match="Expense not found"):
        budget.edit_expense(other, injected, "2026-07", "Changed", "9")
    for name, tag, message in (
        (" ", "", "name is required"), ("Fuel", "x" * 51, "50 characters")
    ):
        with pytest.raises(ValueError, match=message):
            budget.edit_expense(first, injected, "2026-07", name, "9", tag=tag)
    with pytest.raises(ValueError, match="Expense not found"):
        budget.delete_expense(other, injected)
    assert budget.view(other, "2026-07").expenses == ()
    budget.edit_expense(first, injected, "2026-07", "+Invoice", "21.00", "2026-07-02", "Travel")
    changed = next(row for row in budget.view(first, "2026-07").expenses if row.id == injected)
    assert (changed.name, changed.amount_cents, changed.tag) == ("+Invoice", 2100, "Travel")
    edited_csv = list(csv.DictReader(StringIO(budget.export_csv(first, "2026-07", tag="Travel"))))
    assert edited_csv[0]["Expense"] == "'+Invoice"
    storage.close()


def test_v2_upgrade_snapshot_and_new_database_schema(tmp_path: Path) -> None:
    path = tmp_path / "old.db"
    with closing(sqlite3.connect(path)) as db:
        db.executescript("""
            CREATE TABLE profiles (
                id INTEGER PRIMARY KEY, name VARCHAR(100) NOT NULL,
                username VARCHAR(80), password_hash VARCHAR(200));
            CREATE TABLE tasks (
                id INTEGER PRIMARY KEY, profile_id INTEGER NOT NULL,
                title VARCHAR(200) NOT NULL, completed BOOLEAN NOT NULL,
                created_at VARCHAR(40) NOT NULL, completed_at VARCHAR(40),
                FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE);
            INSERT INTO profiles VALUES (1, 'Home', 'alice', 'synthetic-hash');
            INSERT INTO tasks VALUES (1, 1, 'Keep me', 0, '2026-01-01', NULL);
            PRAGMA user_version=2;
        """)
    storage = Storage(path)
    assert storage.profile_name(1) == "Home"
    assert BudgetService(storage).view(1, "2026-07").expenses == ()
    storage.close()
    with closing(sqlite3.connect(path.with_name("old.db.pre-budget-v2"))) as snapshot:
        assert snapshot.execute("PRAGMA user_version").fetchone()[0] == 2
        assert snapshot.execute("SELECT title FROM tasks").fetchone()[0] == "Keep me"
    with closing(sqlite3.connect(path)) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 17
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
