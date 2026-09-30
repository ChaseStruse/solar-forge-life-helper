"""Profile-scoped Easy Budget rules with exact integer-cent storage."""

import csv
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from io import StringIO

from sqlalchemy import select

from solar_forge_desktop.storage import Expense, MonthlyIncome, Profile, Storage

DEFAULT_TAGS = ("House", "Subscriptions", "Car")
RECURRENCES = frozenset({"none", "weekly", "biweekly", "monthly"})
SORT_COLUMNS = frozenset({"name", "tag", "due_date", "amount"})
MONTH_PATTERN = re.compile(r"^\d{4}-\d{2}$")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True)
class ExpenseItem:
    id: int
    name: str
    amount_cents: int
    due_date: str | None
    month_year: str
    tag: str | None
    parent_id: int | None
    recurrence: str


@dataclass(frozen=True)
class BudgetView:
    month_year: str
    income_cents: int
    total_expenses_cents: int
    savings_cents: int
    expenses: tuple[ExpenseItem, ...]
    tags: tuple[str, ...]


def current_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def month_bounds(month: str) -> tuple[date, date]:
    if not MONTH_PATTERN.fullmatch(month or ""):
        raise ValueError("Month must be in YYYY-MM format.")
    try:
        first = date.fromisoformat(month + "-01")
    except ValueError as exc:
        raise ValueError("Month must be in YYYY-MM format.") from exc
    next_month = date(first.year + (first.month == 12), first.month % 12 + 1, 1)
    return first, next_month - timedelta(days=1)


def money_cents(raw: str, *, income: bool) -> int:
    try:
        amount = Decimal(str(raw))
        if not amount.is_finite():
            raise InvalidOperation
        if (income and amount < 0) or (not income and amount <= 0):
            raise ValueError(
                "Income amount cannot be negative."
                if income else "Expense amount must be greater than zero."
            )
        cents = int((amount * 100).quantize(Decimal("1")))
        if cents > 9_999_999_999:
            raise ValueError("Amount is too large.")
        return cents
    except (InvalidOperation, TypeError) as exc:
        raise ValueError(
            "Invalid income amount. Please enter a valid decimal number."
            if income else "Invalid expense amount. Please enter a valid decimal number."
        ) from exc


def format_money(cents: int) -> str:
    return f"${Decimal(cents) / 100:,.2f}"


def safe_csv_cell(value: str) -> str:
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value


def _due_date(raw: str, month: str) -> str | None:
    if not raw or not raw.strip():
        return None
    clean = raw.strip()
    if not DATE_PATTERN.fullmatch(clean):
        raise ValueError("Due date must be in YYYY-MM-DD format.")
    try:
        parsed = date.fromisoformat(clean)
    except ValueError as exc:
        raise ValueError("Due date must be in YYYY-MM-DD format.") from exc
    if parsed.strftime("%Y-%m") != month:
        raise ValueError(
            f"Due date ({clean}) must fall within the active budget month ({month})."
        )
    return parsed.isoformat()


def _occurrences(parent: Expense, first: date, last: date) -> list[date]:
    origin = date.fromisoformat(parent.due_date)
    if parent.recurrence == "monthly":
        return [date(first.year, first.month, min(origin.day, last.day))]
    if parent.recurrence == "weekly":
        start = first + timedelta(days=(origin.weekday() - first.weekday()) % 7)
        step = timedelta(days=7)
    elif parent.recurrence == "biweekly":
        start = origin
        step = timedelta(days=14)
    else:
        return []
    dates = []
    while start <= last:
        if start >= first:
            dates.append(start)
        start += step
    return dates


class BudgetService:
    def __init__(self, storage: Storage):
        self.storage = storage

    @staticmethod
    def _require_profile(session, profile_id: int) -> None:
        if session.get(Profile, profile_id) is None:
            raise ValueError("Profile not found.")

    @staticmethod
    def _child(parent: Expense, due: date, month: str) -> Expense:
        return Expense(
            profile_id=parent.profile_id, name=parent.name,
            amount_cents=parent.amount_cents, due_date=due.isoformat(),
            month_year=month, tag=parent.tag, parent_id=parent.id, recurrence="none",
        )

    def set_income(self, profile_id: int, month: str, amount: str) -> None:
        month_bounds(month)
        cents = money_cents(amount, income=True)
        with self.storage.sessions.begin() as session:
            self._require_profile(session, profile_id)
            income = session.scalar(
                select(MonthlyIncome).where(
                    MonthlyIncome.profile_id == profile_id, MonthlyIncome.month_year == month
                )
            )
            if income is None:
                session.add(MonthlyIncome(
                    profile_id=profile_id, month_year=month, amount_cents=cents
                ))
            else:
                income.amount_cents = cents

    def add_expense(
        self, profile_id: int, month: str, name: str, amount: str,
        due_date: str = "", tag: str = "", recurrence: str = "none",
    ) -> int:
        _, last = month_bounds(month)
        clean_name = (name or "").strip()
        clean_tag = (tag or "").strip()
        if len(clean_tag) > 50:
            raise ValueError("Tag must be 50 characters or fewer.")
        if not clean_name:
            raise ValueError("Expense name is required.")
        cents = money_cents(amount, income=False)
        due = _due_date(due_date, month)
        repeat = recurrence.lower().strip() if recurrence in RECURRENCES else "none"
        if due is None:
            repeat = "none"
        with self.storage.sessions.begin() as session:
            self._require_profile(session, profile_id)
            parent = Expense(
                profile_id=profile_id, month_year=month, name=clean_name,
                amount_cents=cents, due_date=due, tag=clean_tag or None,
                recurrence=repeat,
            )
            session.add(parent)
            session.flush()
            if repeat in {"weekly", "biweekly"}:
                step = timedelta(days=7 if repeat == "weekly" else 14)
                occurrence = date.fromisoformat(due) + step
                while occurrence <= last:
                    session.add(self._child(parent, occurrence, month))
                    occurrence += step
            return parent.id

    def edit_expense(
        self, profile_id: int, expense_id: int, month: str,
        name: str, amount: str, due_date: str = "", tag: str = "",
    ) -> None:
        month_bounds(month)
        clean_name = (name or "").strip()
        clean_tag = (tag or "").strip()
        if len(clean_tag) > 50:
            raise ValueError("Tag must be 50 characters or fewer.")
        if not clean_name:
            raise ValueError("Expense name is required.")
        cents = money_cents(amount, income=False)
        due = _due_date(due_date, month)
        with self.storage.sessions.begin() as session:
            expense = session.scalar(select(Expense).where(
                Expense.id == expense_id, Expense.profile_id == profile_id
            ))
            if expense is None:
                raise ValueError("Expense not found.")
            expense.name = clean_name
            expense.amount_cents = cents
            expense.due_date = due
            expense.tag = clean_tag or None

    def delete_expense(self, profile_id: int, expense_id: int) -> None:
        with self.storage.sessions.begin() as session:
            expense = session.scalar(select(Expense).where(
                Expense.id == expense_id, Expense.profile_id == profile_id
            ))
            if expense is None:
                raise ValueError("Expense not found.")
            session.delete(expense)

    def view(
        self, profile_id: int, month: str, tag: str = "",
        sort_by: str = "due_date", direction: str = "asc",
    ) -> BudgetView:
        first, last = month_bounds(month)
        sort_by = sort_by if sort_by in SORT_COLUMNS else "due_date"
        direction = direction if direction in {"asc", "desc"} else "asc"
        with self.storage.sessions.begin() as session:
            self._require_profile(session, profile_id)
            income = session.scalar(select(MonthlyIncome).where(
                MonthlyIncome.profile_id == profile_id, MonthlyIncome.month_year == month
            ))
            if income is None:
                previous = session.scalar(select(MonthlyIncome).where(
                    MonthlyIncome.profile_id == profile_id, MonthlyIncome.month_year < month
                ).order_by(MonthlyIncome.month_year.desc()).limit(1))
                if previous is not None:
                    income = MonthlyIncome(
                        profile_id=profile_id, month_year=month,
                        amount_cents=previous.amount_cents,
                    )
                    session.add(income)
            parents = session.scalars(select(Expense).where(
                Expense.profile_id == profile_id, Expense.parent_id.is_(None),
                Expense.recurrence != "none", Expense.due_date.is_not(None),
                Expense.month_year < month,
            )).all()
            for parent in parents:
                existing = session.scalars(select(Expense.due_date).where(
                    Expense.profile_id == profile_id, Expense.parent_id == parent.id,
                    Expense.month_year == month,
                )).all()
                if existing:
                    continue
                for occurrence in _occurrences(parent, first, last):
                    session.add(self._child(parent, occurrence, month))
            session.flush()
            rows = session.scalars(select(Expense).where(
                Expense.profile_id == profile_id, Expense.month_year == month
            ).order_by(Expense.due_date.asc(), Expense.id.desc())).all()
            income_cents = income.amount_cents if income is not None else 0
            total = sum(row.amount_cents for row in rows)
            tags = tuple(sorted(
                set(DEFAULT_TAGS) | {row.tag for row in rows if row.tag}, key=str.casefold
            ))
            visible = [row for row in rows if not tag or row.tag == tag]
            key = {
                "name": lambda row: row.name.casefold(),
                "tag": lambda row: row.tag.casefold(),
                "due_date": lambda row: row.due_date,
                "amount": lambda row: row.amount_cents,
            }[sort_by]
            attribute = "amount_cents" if sort_by == "amount" else sort_by
            present = [row for row in visible if getattr(row, attribute) is not None]
            missing = [row for row in visible if row not in present]
            sorted_rows = sorted(present, key=key, reverse=direction == "desc") + missing
            items = tuple(ExpenseItem(
                row.id, row.name, row.amount_cents, row.due_date,
                row.month_year, row.tag, row.parent_id, row.recurrence,
            ) for row in sorted_rows)
            return BudgetView(month, income_cents, total, income_cents - total, items, tags)

    def export_csv(
        self, profile_id: int, month: str, tag: str = "",
        sort_by: str = "due_date", direction: str = "asc",
    ) -> str:
        view = self.view(profile_id, month, tag, sort_by, direction)
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(("Expense", "Amount", "Due Date", "Month", "Tag", "Recurrence"))
        for expense in view.expenses:
            writer.writerow((
                safe_csv_cell(expense.name), f"{Decimal(expense.amount_cents) / 100:.2f}",
                expense.due_date or "", expense.month_year,
                safe_csv_cell(expense.tag or ""), expense.recurrence,
            ))
        return output.getvalue()
