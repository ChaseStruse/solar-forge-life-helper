"""Qt Widgets Easy Budget page modeled on the web layout and interactions."""

import os
import tempfile
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QDate, QEvent, Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QBoxLayout,
    QComboBox,
    QDateEdit,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from solar_forge_desktop.budget import (
    BudgetService,
    BudgetView,
    ExpenseItem,
    current_month,
    format_money,
)
from solar_forge_desktop.calendar_widgets import CALENDAR_STYLE, SELECTOR_STYLE, style_calendar
from solar_forge_desktop.workers import BackgroundWorker

STYLE = """
QWidget#budgetPage, QWidget#budgetBody { background: #0a0712; color: #f3f4f6; }
QScrollArea#budgetScroll, QScrollArea#budgetScroll QWidget#qt_scrollarea_viewport {
    background: #0a0712; border: none; }
QFrame#budgetCard, QFrame#budgetIncomeKpi, QFrame#budgetExpensesKpi,
QFrame#budgetSavingsKpi { background: #151027; border: 1px solid #2b2340;
    border-radius: 16px; }
QFrame#budgetIncomeKpi { border-left: 4px solid #10b981; }
QFrame#budgetExpensesKpi { border-left: 4px solid #f43f5e; }
QFrame#budgetSavingsKpi { border-left: 4px solid #06b6d4; }
QLabel#budgetTitle { color: #f3f4f6; font-size: 32px; font-weight: 700; }
QLabel#budgetSubtitle { color: #a1a1aa; font-size: 14px; }
QLabel#budgetKpiTitle, QLabel#budgetFieldLabel { color: #a1a1aa;
    font-size: 12px; font-weight: 600; }
QLabel#budgetIncomeValue { color: #10b981; font-size: 29px; font-weight: 700; }
QLabel#budgetExpensesValue { color: #f43f5e; font-size: 29px; font-weight: 700; }
QLabel#budgetSavingsValue { color: #06b6d4; font-size: 29px; font-weight: 700; }
QLabel#budgetKpiDescription, QLabel#budgetEmptyHint { color: #71717a; font-size: 12px; }
QLabel#budgetCardTitle { color: #f3f4f6; font-size: 18px; font-weight: 700; }
QLabel#budgetEmptyTitle { color: #a1a1aa; font-size: 16px; }
QLabel#budgetStatus { color: #fb7185; }
QLineEdit, QDateEdit, QComboBox { background: #211b30; color: #f3f4f6;
    border: 1px solid #302943; border-radius: 9px; padding: 10px 12px;
    min-height: 22px; }
QLineEdit:focus, QDateEdit:focus, QComboBox:focus { border-color: #8b5cf6; }
QPushButton#budgetPrimary { color: white; border: none; border-radius: 10px;
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #8b5cf6,stop:1 #ec4899);
    padding: 11px 14px; font-weight: 700; }
QPushButton#budgetSecondary, QPushButton#budgetEdit, QPushButton#budgetCancel {
    background: #292143; color: #f3f4f6; border: 1px solid #483a64;
    border-radius: 9px; padding: 8px 12px; }
QPushButton#budgetDelete { background: #3a1d39; color: #fb7185;
    border: 1px solid #5b3048; border-radius: 9px; padding: 8px 12px; }
QTableWidget#budgetTable { background: #151027; color: #f3f4f6; border: none;
    gridline-color: transparent; selection-background-color: #151027; }
QTableWidget#budgetTable QHeaderView::section { background: #151027; color: #a1a1aa;
    border: none; border-bottom: 1px solid #302943; padding: 8px 4px;
    font-size: 11px; font-weight: 700; }
QTableWidget#budgetTable::item { border-bottom: 1px solid #302943; padding: 6px; }

""" + CALENDAR_STYLE + SELECTOR_STYLE


def _label(text: str, name: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName(name)
    label.setTextFormat(Qt.TextFormat.PlainText)
    return label


def _field(text: str, placeholder: str = "", max_length: int = 100) -> QLineEdit:
    field = QLineEdit()
    field.setAccessibleName(text)
    field.setPlaceholderText(placeholder)
    field.setMaxLength(max_length)
    return field


class BudgetDateEdit(QDateEdit):
    """Keep an optional date empty while opening its built-in popup on today."""

    def __init__(self):
        super().__init__()
        self.setCalendarPopup(True)
        self._calendar = self.calendarWidget()
        style_calendar(self._calendar)
        self._calendar.installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:
        if watched is self._calendar and event.type() == QEvent.Type.Show:
            QTimer.singleShot(0, self._show_current_month)
        return super().eventFilter(watched, event)

    def _show_current_month(self) -> None:
        if self._calendar.isVisible() and self.date() == self.minimumDate():
            today = QDate.currentDate()
            self._calendar.setCurrentPage(today.year(), today.month())


class BudgetPage(QWidget):
    def __init__(self, service: BudgetService, profile_id: int):
        super().__init__()
        self.service = service
        self.profile_id = profile_id
        self.month = current_month()
        self.sort_by = "due_date"
        self.direction = "asc"
        self._view_serial = 0
        self.setObjectName("budgetPage")
        self.setStyleSheet(STYLE)
        self._build()
        self._worker = BackgroundWorker(self, "solar-forge-budget")
        self._worker.busy_changed.connect(self._set_busy)
        self._worker.failed.connect(self._show_error)

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setObjectName("budgetScroll")
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        body = QWidget()
        body.setObjectName("budgetBody")
        scroll.setWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(48, 36, 48, 40)
        layout.setSpacing(0)

        heading_row = QHBoxLayout()
        self.heading_row = heading_row
        heading_text = QVBoxLayout()
        heading_text.setSpacing(4)
        heading_text.addWidget(_label("Easy Budget", "budgetTitle"))
        subtitle = _label(
            "Track base income, set monthly expenses, and monitor net savings.",
            "budgetSubtitle",
        )
        subtitle.setWordWrap(True)
        heading_text.addWidget(subtitle)
        heading_row.addLayout(heading_text, 1)
        self.month_picker = QDateEdit()
        self.month_picker.setObjectName("budgetMonth")
        self.month_picker.setAccessibleName("Budget month")
        self.month_picker.setCalendarPopup(True)
        style_calendar(self.month_picker.calendarWidget())
        self.month_picker.setDisplayFormat("MMMM yyyy")
        self.month_picker.setDate(QDate.fromString(self.month + "-01", "yyyy-MM-dd"))
        self.month_picker.setFixedWidth(195)
        self.month_picker.dateChanged.connect(self._month_changed)
        heading_row.addWidget(self.month_picker, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(heading_row)
        layout.addSpacing(45)

        kpis = QHBoxLayout()
        self.kpis = kpis
        kpis.setSpacing(24)
        self.income_value = self._kpi(
            kpis, "budgetIncomeKpi", "MONTHLY INCOME", "budgetIncomeValue",
            "Base cash pool for " + datetime.strptime(self.month, "%Y-%m").strftime("%B %Y"),
        )
        self.expenses_value = self._kpi(
            kpis, "budgetExpensesKpi", "TOTAL EXPENSES", "budgetExpensesValue",
            "Total outgoing expenses logged",
        )
        self.savings_value = self._kpi(
            kpis, "budgetSavingsKpi", "NET SAVINGS", "budgetSavingsValue",
            "Available cash remaining",
        )
        layout.addLayout(kpis)
        layout.addSpacing(9)
        self.status = _label("", "budgetStatus")
        self.status.setAccessibleName("Budget status")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        layout.addSpacing(9)

        columns = QHBoxLayout()
        self.columns = columns
        columns.setSpacing(24)
        forms = QVBoxLayout()
        forms.setSpacing(24)
        forms.addWidget(self._income_card())
        forms.addWidget(self._expense_card())
        forms.addStretch()
        columns.addLayout(forms, 1)
        columns.addWidget(self._table_card(), 2, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(columns)
        layout.addStretch()
        self._apply_responsive()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_responsive()

    def _apply_responsive(self) -> None:
        compact = self.width() < 820
        direction = (
            QBoxLayout.Direction.TopToBottom if compact
            else QBoxLayout.Direction.LeftToRight
        )
        self.heading_row.setDirection(direction)
        self.kpis.setDirection(direction)
        self.columns.setDirection(direction)
        self.kpis.setSpacing(16 if compact else 24)
        self.columns.setSpacing(20 if compact else 24)

    def _kpi(
        self, container: QHBoxLayout, card_name: str, title: str,
        value_name: str, description: str,
    ) -> QLabel:
        card = QFrame()
        card.setObjectName(card_name)
        card.setMinimumHeight(132)
        column = QVBoxLayout(card)
        column.setContentsMargins(24, 20, 18, 18)
        column.setSpacing(4)
        column.addWidget(_label(title, "budgetKpiTitle"))
        value = _label("$0.00", value_name)
        column.addWidget(value)
        desc = _label(description, "budgetKpiDescription")
        desc.setWordWrap(True)
        column.addWidget(desc)
        column.addStretch()
        container.addWidget(card, 1)
        if card_name == "budgetIncomeKpi":
            self.income_description = desc
        return value

    @staticmethod
    def _card(title: str) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("budgetCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(10)
        layout.addWidget(_label(title, "budgetCardTitle"))
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #302943;")
        layout.addWidget(line)
        layout.addSpacing(6)
        return card, layout

    @staticmethod
    def _form_field(layout: QVBoxLayout, label: str, field: QWidget) -> None:
        layout.addWidget(_label(label.upper(), "budgetFieldLabel"))
        layout.addWidget(field)
        layout.addSpacing(8)

    def _income_card(self) -> QFrame:
        card, layout = self._card("Set Income")
        self.income_input = _field("Monthly Base Income ($)", "e.g. 4500.00")
        self.income_input.setObjectName("incomeAmount")
        self._form_field(layout, "Monthly Base Income ($)", self.income_input)
        self.income_button = QPushButton("Update Income")
        self.income_button.setObjectName("budgetPrimary")
        self.income_button.setAccessibleName("Update Income")
        self.income_button.clicked.connect(self.update_income)
        layout.addWidget(self.income_button)
        return card

    def _date_input(self, name: str) -> QDateEdit:
        picker = BudgetDateEdit()
        picker.setObjectName(name)
        picker.setAccessibleName("Due Date (Optional)")
        picker.setMinimumDate(QDate(1900, 1, 1))
        picker.setDate(picker.minimumDate())
        picker.setSpecialValueText("mm/dd/yyyy")
        picker.setDisplayFormat("MM/dd/yyyy")
        return picker

    def _expense_card(self) -> QFrame:
        card, layout = self._card("Add Expense")
        self.name_input = _field("Expense Name", "e.g. Rent, Electric Bill")
        self.name_input.setObjectName("expenseName")
        self._form_field(layout, "Expense Name", self.name_input)
        self.amount_input = _field("Amount ($)", "e.g. 1200.00")
        self.amount_input.setObjectName("expenseAmount")
        self._form_field(layout, "Amount ($)", self.amount_input)
        self.tag_input = _field("Tag (Optional)", "e.g. House", 50)
        self.tag_input.setObjectName("expenseTag")
        self._form_field(layout, "Tag (Optional)", self.tag_input)
        self.due_input = self._date_input("expenseDueDate")
        self._form_field(layout, "Due Date (Optional)", self.due_input)
        self.recurrence_label = _label("RECURRENCE", "budgetFieldLabel")
        layout.addWidget(self.recurrence_label)
        self.recurrence_input = QComboBox()
        self.recurrence_input.setObjectName("expenseRecurrence")
        self.recurrence_input.setAccessibleName("Recurrence")
        for label, value in (
            ("One-time Expense", "none"), ("Weekly", "weekly"),
            ("Bi-weekly", "biweekly"), ("Monthly", "monthly"),
        ):
            self.recurrence_input.addItem(label, value)
        layout.addWidget(self.recurrence_input)
        self.due_input.dateChanged.connect(self._toggle_recurrence)
        self._toggle_recurrence()
        layout.addSpacing(8)
        self.expense_button = QPushButton("Add Expense")
        self.expense_button.setObjectName("budgetPrimary")
        self.expense_button.setAccessibleName("Add Expense")
        self.expense_button.clicked.connect(self.add_expense)
        layout.addWidget(self.expense_button)
        return card

    def _table_card(self) -> QFrame:
        card, layout = self._card("Logged Expenses (0)")
        self.table_heading = card.findChild(QLabel, "budgetCardTitle")
        filter_row = QHBoxLayout()
        filter_column = QVBoxLayout()
        filter_column.setSpacing(6)
        filter_column.addWidget(_label("FILTER BY TAG", "budgetFieldLabel"))
        self.tag_filter = QComboBox()
        self.tag_filter.setObjectName("budgetTagFilter")
        self.tag_filter.setAccessibleName("Filter by tag")
        self.tag_filter.addItem("All tags", "")
        self.tag_filter.currentIndexChanged.connect(self.refresh)
        filter_column.addWidget(self.tag_filter)
        filter_row.addLayout(filter_column, 1)
        self.export_button = QPushButton("Export CSV")
        self.export_button.setObjectName("budgetSecondary")
        self.export_button.setAccessibleName("Export CSV")
        self.export_button.clicked.connect(self.export_csv)
        filter_row.addWidget(self.export_button, 0, Qt.AlignmentFlag.AlignBottom)
        layout.addLayout(filter_row)
        layout.addSpacing(14)

        self.empty = QWidget()
        empty_layout = QVBoxLayout(self.empty)
        empty_layout.setContentsMargins(0, 38, 0, 38)
        empty_layout.setSpacing(6)
        icon = _label("⊖", "budgetEmptyTitle")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet("font-size: 42px; color: #5b5467;")
        empty_layout.addWidget(icon)
        title = _label("No expenses recorded this month.", "budgetEmptyTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(title)
        hint = _label("Use the forms on the left to catalog your costs.", "budgetEmptyHint")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(hint)
        layout.addWidget(self.empty)

        self.table = QTableWidget(0, 5)
        self.table.setObjectName("budgetTable")
        self.table.setHorizontalHeaderLabels(
            ["Expense Item", "Tag", "Due Date", "Amount", "Action"]
        )
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column, width in ((1, 72), (2, 108), (3, 96), (4, 96)):
            self.table.setColumnWidth(column, width)
        self.table.horizontalHeader().sectionClicked.connect(self._sort_column)
        self.table.verticalHeader().hide()
        self.table.setShowGrid(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.setMinimumHeight(180)
        layout.addWidget(self.table)
        self.table.hide()
        return card

    def activate(self) -> None:
        self.refresh()

    def _month_changed(self) -> None:
        self.month = self.month_picker.date().toString("yyyy-MM")
        if self.due_input.date() != self.due_input.minimumDate():
            self.due_input.setDate(self.due_input.minimumDate())
        self.refresh()

    def _toggle_recurrence(self) -> None:
        has_date = self.due_input.date() != self.due_input.minimumDate()
        self.recurrence_label.setVisible(has_date)
        self.recurrence_input.setVisible(has_date)
        if not has_date:
            self.recurrence_input.setCurrentIndex(0)

    def _due_text(self, picker: QDateEdit) -> str:
        return "" if picker.date() == picker.minimumDate() else picker.date().toString("yyyy-MM-dd")

    def _run(self, action: Callable[[], object], done: Callable[[object], None]) -> None:
        self._worker.submit(action, done)

    def _set_busy(self, busy: bool) -> None:
        self.income_button.setEnabled(not busy)
        self.expense_button.setEnabled(not busy)

    def _show_error(self, error: Exception) -> None:
        self.status.setText(
            str(error) if isinstance(error, ValueError) else
            "The budget could not be saved. Check the data location and try again."
        )
        self.status.setStyleSheet("color: #fb7185;")

    def refresh(self) -> None:
        tag = self.tag_filter.currentData() or ""
        month = self.month
        sort_by = self.sort_by
        direction = self.direction
        self._view_serial += 1
        serial = self._view_serial
        self._run(
            lambda: self.service.view(self.profile_id, month, tag, sort_by, direction),
            lambda result: self._render(result) if serial == self._view_serial else None,
        )

    def _render(self, result: object) -> None:
        view: BudgetView = result
        if view.month_year != self.month:
            return
        self.income_value.setText(format_money(view.income_cents))
        self.expenses_value.setText(format_money(view.total_expenses_cents))
        self.savings_value.setText(format_money(view.savings_cents))
        display = datetime.strptime(view.month_year, "%Y-%m").strftime("%B %Y")
        self.income_description.setText("Base cash pool for " + display)
        self.income_input.setText(
            f"{Decimal(view.income_cents) / 100:.2f}" if view.income_cents else ""
        )
        selected = self.tag_filter.currentData() or ""
        self.tag_filter.blockSignals(True)
        self.tag_filter.clear()
        self.tag_filter.addItem("All tags", "")
        for tag in view.tags:
            self.tag_filter.addItem(tag, tag)
        index = self.tag_filter.findData(selected)
        self.tag_filter.setCurrentIndex(max(0, index))
        self.tag_filter.blockSignals(False)
        self.table_heading.setText(f"Logged Expenses ({len(view.expenses)})")
        self.empty.setVisible(not view.expenses)
        self.table.setVisible(bool(view.expenses))
        self.table.setRowCount(len(view.expenses))
        self._rows = {item.id: row for row, item in enumerate(view.expenses)}
        for row, expense in enumerate(view.expenses):
            self.table.setRowHeight(row, 52)
            self._render_row(row, expense)
        self.table.setFixedHeight(min(590, max(180, len(view.expenses) * 52 + 42)))
        labels = ["Expense Item", "Tag", "Due Date", "Amount", "Action"]
        sort_column = {"name": 0, "tag": 1, "due_date": 2, "amount": 3}[self.sort_by]
        labels[sort_column] += " ↑" if self.direction == "asc" else " ↓"
        self.table.setHorizontalHeaderLabels(labels)

    def _render_row(self, row: int, expense: ExpenseItem) -> None:
        due = (
            date.fromisoformat(expense.due_date).strftime("%b %d, %Y")
            if expense.due_date else "—"
        )
        values = (
            expense.name, expense.tag or "—", due,
            "-" + format_money(expense.amount_cents),
        )
        for column, value in enumerate(values):
            self.table.removeCellWidget(row, column)
            cell = QTableWidgetItem(value)
            if column == 0:
                cell.setForeground(QColor("#f3f4f6"))
            elif column == 2 and expense.due_date:
                cell.setForeground(QColor("#818cf8"))
            elif column == 3:
                cell.setForeground(QColor("#f43f5e"))
                cell.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, column, cell)
        actions = QWidget()
        row_layout = QHBoxLayout(actions)
        row_layout.setContentsMargins(2, 1, 2, 1)
        row_layout.setSpacing(5)
        edit = QPushButton("✎")
        edit.setObjectName("budgetEdit")
        edit.setAccessibleName(f"Edit {expense.name}")
        edit.clicked.connect(lambda _checked=False, item=expense: self._begin_edit(item))
        row_layout.addWidget(edit)
        delete = QPushButton("⌫")
        delete.setObjectName("budgetDelete")
        delete.setAccessibleName(f"Delete {expense.name}")
        delete.clicked.connect(lambda _checked=False, item=expense: self._confirm_delete(item))
        row_layout.addWidget(delete)
        self.table.setCellWidget(row, 4, actions)

    def _sort_column(self, column: int) -> None:
        keys = {0: "name", 1: "tag", 2: "due_date", 3: "amount"}
        if column not in keys:
            return
        selected = keys[column]
        self.direction = "desc" if self.sort_by == selected and self.direction == "asc" else "asc"
        self.sort_by = selected
        self.refresh()

    def update_income(self) -> None:
        amount = self.income_input.text()
        month = self.month
        self._run(
            lambda: self.service.set_income(self.profile_id, month, amount),
            lambda _: self._after_save("Income updated successfully!"),
        )

    def add_expense(self) -> None:
        month = self.month
        name = self.name_input.text()
        amount = self.amount_input.text()
        tag = self.tag_input.text()
        due = self._due_text(self.due_input)
        repeat = self.recurrence_input.currentData()
        self._run(
            lambda: self.service.add_expense(
                self.profile_id, month, name, amount, due, tag, repeat
            ),
            lambda _: self._after_add(repeat),
        )

    def _after_save(self, message: str) -> None:
        self.status.setText(message)
        self.status.setStyleSheet("color: #10b981;")
        self.refresh()

    def _after_add(self, recurrence: str) -> None:
        self.name_input.clear()
        self.amount_input.clear()
        self.tag_input.clear()
        self.due_input.setDate(self.due_input.minimumDate())
        message = (
            f"Recurring expense added successfully ({recurrence})!"
            if recurrence != "none" else "Expense added successfully!"
        )
        self._after_save(message)

    def _begin_edit(self, expense: ExpenseItem) -> None:
        row = self._rows.get(expense.id)
        if row is None:
            return
        name = _field("Expense Name")
        name.setText(expense.name)
        tag = _field("Tag", max_length=50)
        tag.setText(expense.tag or "")
        due = self._date_input(f"editDueDate_{expense.id}")
        if expense.due_date:
            due.setDate(QDate.fromString(expense.due_date, "yyyy-MM-dd"))
        amount = _field("Amount")
        amount.setText(f"{Decimal(expense.amount_cents) / 100:.2f}")
        for column, widget in enumerate((name, tag, due, amount)):
            self.table.setCellWidget(row, column, widget)
        actions = QWidget()
        row_layout = QHBoxLayout(actions)
        row_layout.setContentsMargins(2, 1, 2, 1)
        save = QPushButton("✓")
        save.setObjectName("budgetPrimary")
        save.setAccessibleName(f"Save {expense.name}")
        save.clicked.connect(
            lambda: self._save_edit(expense.id, name.text(), amount.text(),
                                    self._due_text(due), tag.text())
        )
        row_layout.addWidget(save)
        cancel = QPushButton("✕")
        cancel.setObjectName("budgetCancel")
        cancel.setAccessibleName("Cancel edit")
        cancel.clicked.connect(self.refresh)
        row_layout.addWidget(cancel)
        self.table.setCellWidget(row, 4, actions)
        name.setFocus()

    def _save_edit(
        self, expense_id: int, name: str, amount: str, due: str, tag: str,
    ) -> None:
        month = self.month
        self._run(
            lambda: self.service.edit_expense(
                self.profile_id, expense_id, month, name, amount, due, tag
            ),
            lambda _: self._after_save("Expense updated successfully!"),
        )

    def _confirm_delete(self, expense: ExpenseItem) -> None:
        dialog = QDialog(self)
        dialog.setObjectName("budgetDeleteDialog")
        dialog.setWindowTitle("Delete expense")
        dialog.setStyleSheet("""
            QDialog#budgetDeleteDialog { background: #1a1533; color: #f3f4f6; }
            QLabel { color: #f3f4f6; }
            QPushButton { background: #292143; color: #f3f4f6; padding: 10px 16px;
                border: 1px solid #483a64; border-radius: 9px; }
            QPushButton#confirmBudgetDelete { background: #be3153; border-color: #e44970; }
        """)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(24, 24, 24, 24)
        heading = QLabel("Delete expense?")
        heading.setStyleSheet("font-size: 18px; font-weight: 700;")
        layout.addWidget(heading)
        message = QLabel(f"Delete '{expense.name}'?")
        message.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(message)
        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(dialog.reject)
        cancel.setDefault(True)
        buttons.addWidget(cancel)
        confirm = QPushButton("Delete expense")
        confirm.setObjectName("confirmBudgetDelete")
        confirm.clicked.connect(dialog.accept)
        buttons.addWidget(confirm)
        layout.addLayout(buttons)
        cancel.setFocus()
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._run(
                lambda: self.service.delete_expense(self.profile_id, expense.id),
                lambda _: self._after_save("Expense deleted."),
            )

    def export_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export budget CSV", f"budget-{self.month}.csv", "CSV files (*.csv)"
        )
        if not path:
            return
        month = self.month
        tag = self.tag_filter.currentData() or ""
        sort_by, direction = self.sort_by, self.direction

        def write_export() -> None:
            contents = self.service.export_csv(self.profile_id, month, tag, sort_by, direction)
            destination = Path(path)
            fd, temporary_name = tempfile.mkstemp(
                prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
            )
            temporary = Path(temporary_name)
            try:
                with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
                    stream.write(contents)
                os.replace(temporary, destination)
            finally:
                temporary.unlink(missing_ok=True)

        self._run(write_export, lambda _: self._after_save("CSV exported successfully."))

    def shutdown(self) -> None:
        self._worker.shutdown()
