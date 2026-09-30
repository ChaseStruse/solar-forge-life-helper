"""Native Habit Tracker page matching the web weekly grid."""

from datetime import date, timedelta
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QBoxLayout,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from solar_forge_desktop.habits import HabitItem, HabitService, HabitWeek, week_start
from solar_forge_desktop.workers import BackgroundWorker

STYLE = """
QWidget#habitPage, QWidget#habitBody { background: #0a0712; }
QWidget#habitGridBody { background: #1a1533; }
QScrollArea#habitScroll, QScrollArea#habitGridScroll { background: transparent; border: none; }
QFrame#habitPanel { background: #1a1533; border: 1px solid #302943; border-radius: 16px; }
QLabel#habitEyebrow { color: #ec4899; font-size: 11px; font-weight: 700; }
QLabel#habitTitle { color: #f3f4f6; font-size: 32px; font-weight: 700; }
QLabel#habitHeading { color: #f3f4f6; font-size: 18px; font-weight: 700; }
QLabel#habitText { color: #f3f4f6; font-size: 14px; }
QLabel#habitMuted { color: #a1a1aa; }
QLabel#habitStatus { color: #fb7185; }
QLabel#habitPercent { color: #8b5cf6; font-size: 18px; font-weight: 700; }
QLineEdit#habitInput { background: #211b30; color: #f3f4f6;
    border: 1px solid #302943; border-radius: 9px; padding: 10px 12px; }
QLineEdit#habitInput:focus { border-color: #8b5cf6; }
QPushButton#habitPrimary { background: #8b5cf6; color: white; border: none;
    border-radius: 9px; padding: 10px 16px; font-weight: 700; }
QPushButton#habitWeekButton { background: #292143; color: #f3f4f6;
    border: 1px solid #483a64; border-radius: 9px; padding: 7px 13px; }
QPushButton#habitDelete { background: transparent; color: #a1a1aa;
    border: none; font-size: 20px; padding: 4px; }
QPushButton#habitCheck { background: #211b30; color: white;
    border: 1px solid #483a64; border-radius: 10px; font-size: 16px; }
QPushButton#habitCheck:checked { background: #8b5cf6; border-color: #a78bfa; }
QProgressBar#habitProgress { background: #211b30; border: none; border-radius: 4px; }
QProgressBar#habitProgress::chunk { background: #8b5cf6; border-radius: 4px; }
"""


def _label(value: str, name: str) -> QLabel:
    label = QLabel(value)
    label.setObjectName(name)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    return label


class HabitPage(QWidget):
    def __init__(self, service: HabitService, profile_id: int):
        super().__init__()
        self.service = service
        self.profile_id = profile_id
        self.selected_week = week_start(date.today())
        self._serial = 0
        self._grid_rows = 0
        self.check_buttons: dict[tuple[int, date], QPushButton] = {}
        self.check_icon = QIcon(str(Path(__file__).parent / "assets" / "habit-check.svg"))
        self.setObjectName("habitPage")
        self.setStyleSheet(STYLE)
        self._build()
        self._worker = BackgroundWorker(self, "solar-forge-habits")
        self._worker.busy_changed.connect(self._set_busy)
        self._worker.failed.connect(self._show_error)

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setObjectName("habitScroll")
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        body = QWidget()
        body.setObjectName("habitBody")
        scroll.setWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(48, 36, 48, 40)
        layout.setSpacing(16)
        layout.addWidget(_label("SMALL STEPS", "habitEyebrow"))
        header = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.header = header
        title = QVBoxLayout()
        title.addWidget(_label("Habit Tracker", "habitTitle"))
        title.addWidget(_label("A simple yes or no for each day of the week.", "habitMuted"))
        header.addLayout(title, 1)
        nav = QHBoxLayout()
        self.previous_button = QPushButton("←")
        self.previous_button.setObjectName("habitWeekButton")
        self.previous_button.setAccessibleName("Previous week")
        self.previous_button.clicked.connect(lambda: self._move_week(-7))
        nav.addWidget(self.previous_button)
        self.week_label = _label("", "habitText")
        self.week_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.week_label.setMinimumWidth(150)
        nav.addWidget(self.week_label)
        self.next_button = QPushButton("→")
        self.next_button.setObjectName("habitWeekButton")
        self.next_button.setAccessibleName("Next week")
        self.next_button.clicked.connect(lambda: self._move_week(7))
        nav.addWidget(self.next_button)
        header.addLayout(nav)
        layout.addLayout(header)
        self.status = _label("", "habitStatus")
        self.status.setAccessibleName("Habit status")
        layout.addWidget(self.status)
        summary = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.summary = summary
        self.count_label = _label("0 yes checks this week", "habitText")
        self.count_label.setMinimumWidth(180)
        summary.addWidget(self.count_label)
        self.progress = QProgressBar()
        self.progress.setObjectName("habitProgress")
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(7)
        summary.addWidget(self.progress, 1)
        self.percent_label = _label("0%", "habitPercent")
        summary.addWidget(self.percent_label)
        layout.addLayout(summary)
        panel = QFrame()
        panel.setObjectName("habitPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(20, 20, 20, 20)
        panel_layout.setSpacing(22)
        add_row = QHBoxLayout()
        self.name_input = QLineEdit()
        self.name_input.setObjectName("habitInput")
        self.name_input.setAccessibleName("New habit")
        self.name_input.setPlaceholderText("Add a habit, such as Drink water")
        self.name_input.setMaxLength(100)
        self.name_input.returnPressed.connect(self.add_habit)
        add_row.addWidget(self.name_input, 1)
        self.add_button = QPushButton("Add habit")
        self.add_button.setObjectName("habitPrimary")
        self.add_button.clicked.connect(self.add_habit)
        add_row.addWidget(self.add_button)
        panel_layout.addLayout(add_row)
        grid_scroll = QScrollArea()
        grid_scroll.setObjectName("habitGridScroll")
        grid_scroll.setWidgetResizable(True)
        self.grid_scroll = grid_scroll
        self.grid_body = QWidget()
        self.grid_body.setObjectName("habitGridBody")
        self.grid_body.setMinimumWidth(720)
        self.grid = QGridLayout(self.grid_body)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(10)
        self.grid.setVerticalSpacing(14)
        self.grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        grid_scroll.setWidget(self.grid_body)
        panel_layout.addWidget(grid_scroll)
        layout.addWidget(panel)
        layout.addStretch()
        self._set_week_label()
        self._apply_responsive()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_responsive()

    def _apply_responsive(self) -> None:
        self.header.setDirection(
            QBoxLayout.Direction.TopToBottom if self.width() < 900
            else QBoxLayout.Direction.LeftToRight
        )
        self.summary.setDirection(
            QBoxLayout.Direction.TopToBottom if self.width() < 700
            else QBoxLayout.Direction.LeftToRight
        )

    def _set_week_label(self) -> None:
        end = self.selected_week + timedelta(days=6)
        self.week_label.setText(
            f"{self.selected_week:%b} {self.selected_week.day} – {end:%b} {end.day}"
        )

    def _move_week(self, days: int) -> None:
        self.selected_week += timedelta(days=days)
        self._set_week_label()
        self.refresh()

    def activate(self) -> None:
        self.refresh()

    def _run(self, action: Callable[[], object], done: Callable[[object], None]) -> None:
        self._worker.submit(action, done)

    def _set_busy(self, busy: bool) -> None:
        self.add_button.setEnabled(not busy)

    def _show_error(self, error: Exception) -> None:
        self.status.setText(
            str(error) if isinstance(error, ValueError)
            else "The habit could not be saved. Please try again."
        )
        self.status.setStyleSheet("color: #fb7185;")

    def refresh(self) -> None:
        self._serial += 1
        serial = self._serial
        selected = self.selected_week
        self._run(
            lambda: self.service.view(self.profile_id, selected),
            lambda result: self._render(result) if serial == self._serial else None,
        )

    def _clear_grid(self) -> None:
        self.check_buttons.clear()
        for row in range(self._grid_rows + 1):
            self.grid.setRowMinimumHeight(row, 0)
        self._grid_rows = 0
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget() is not None:
                item.widget().hide()
                item.widget().deleteLater()

    def _render(self, week: HabitWeek) -> None:
        self.count_label.setText(f"{week.completed_count} yes checks this week")
        self.progress.setValue(week.completion_percent)
        self.progress.setAccessibleName(f"{week.completion_percent} percent complete")
        self.percent_label.setText(f"{week.completion_percent}%")
        self._clear_grid()
        if not week.habits:
            self.grid_scroll.setFixedHeight(180)
            empty = QWidget()
            box = QVBoxLayout(empty)
            box.setContentsMargins(12, 40, 12, 40)
            mark = _label("✓", "habitPercent")
            mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
            box.addWidget(mark)
            title = _label("Choose your first habit", "habitHeading")
            title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            box.addWidget(title)
            hint = _label(
                "Try drinking water, stretching, reading, or taking vitamins.", "habitMuted"
            )
            hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
            box.addWidget(hint)
            self.grid.addWidget(empty, 0, 0, 1, 8)
            return
        self.grid_scroll.setFixedHeight(min(430, 70 + 80 * len(week.habits)))
        self._grid_rows = len(week.habits)
        self.grid.setRowMinimumHeight(0, 44)
        self.grid.addWidget(_label("HABIT", "habitMuted"), 0, 0)
        for column, day in enumerate(week.days, start=1):
            heading = _label(f"{day:%a}\n{day.day}", "habitMuted")
            heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid.addWidget(heading, 0, column)
        for row, habit in enumerate(week.habits, start=1):
            self.grid.setRowMinimumHeight(row, 66)
            name_cell = QWidget()
            name_row = QHBoxLayout(name_cell)
            name_row.setContentsMargins(0, 5, 0, 5)
            name_row.addWidget(_label(habit.name, "habitText"), 1)
            delete = QPushButton("×")
            delete.setObjectName("habitDelete")
            delete.setAccessibleName(f"Remove {habit.name}")
            delete.clicked.connect(lambda _checked=False, item=habit: self._confirm_delete(item))
            name_row.addWidget(delete)
            self.grid.addWidget(name_cell, row, 0)
            for column, day in enumerate(week.days, start=1):
                check = QPushButton()
                check.setObjectName("habitCheck")
                check.setFixedSize(34, 34)
                check.setCheckable(True)
                check.setChecked((habit.id, day) in week.checked)
                check.setIcon(self.check_icon if check.isChecked() else QIcon())
                check.setIconSize(QSize(18, 18))
                check.toggled.connect(
                    lambda checked, button=check: button.setIcon(
                        self.check_icon if checked else QIcon()
                    )
                )
                check.setAccessibleName(
                    f"{habit.name} on {day:%A}: "
                    f"{'yes' if check.isChecked() else 'no'}"
                )
                check.clicked.connect(
                    lambda _checked=False, habit_id=habit.id, selected_day=day:
                    self._toggle(habit_id, selected_day)
                )
                cell = QWidget()
                cell_layout = QHBoxLayout(cell)
                cell_layout.setContentsMargins(0, 0, 0, 0)
                cell_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                cell_layout.addWidget(check)
                self.grid.addWidget(cell, row, column)
                self.check_buttons[(habit.id, day)] = check
        self.grid.setColumnStretch(0, 2)
        for column in range(1, 8):
            self.grid.setColumnStretch(column, 1)

    def add_habit(self) -> None:
        name = self.name_input.text()
        self._run(
            lambda: self.service.add(self.profile_id, name),
            lambda _: self._after_add(name.strip()),
        )

    def _after_add(self, name: str) -> None:
        self.name_input.clear()
        self.status.setText(f"Added {name}.")
        self.status.setStyleSheet("color: #10b981;")
        self.refresh()

    def _toggle(self, habit_id: int, day: date) -> None:
        self._run(
            lambda: self.service.toggle(self.profile_id, habit_id, day),
            lambda _: self.refresh(),
        )

    def _confirm_delete(self, habit: HabitItem) -> None:
        dialog = QDialog(self)
        dialog.setObjectName("habitDeleteDialog")
        dialog.setWindowTitle("Remove habit")
        dialog.setStyleSheet("""
            QDialog#habitDeleteDialog { background: #1a1533; color: #f3f4f6; }
            QLabel { color: #f3f4f6; }
            QPushButton { background: #292143; color: #f3f4f6; padding: 10px 16px;
                border: 1px solid #483a64; border-radius: 9px; }
            QPushButton#habitConfirmDelete { background: #be3153; border-color: #e44970; }
        """)
        box = QVBoxLayout(dialog)
        box.setContentsMargins(24, 24, 24, 24)
        box.addWidget(_label(f"Remove {habit.name} and its history?", "habitHeading"))
        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton("Cancel")
        cancel.setDefault(True)
        cancel.clicked.connect(dialog.reject)
        buttons.addWidget(cancel)
        confirm = QPushButton("Remove habit")
        confirm.setObjectName("habitConfirmDelete")
        confirm.clicked.connect(dialog.accept)
        buttons.addWidget(confirm)
        box.addLayout(buttons)
        cancel.setFocus()
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        dialog.deleteLater()
        if accepted:
            self._run(
                lambda: self.service.delete(self.profile_id, habit.id),
                lambda _: self._after_delete(habit.name),
            )

    def _after_delete(self, name: str) -> None:
        self.status.setText(f"Removed {name}.")
        self.status.setStyleSheet("color: #10b981;")
        self.refresh()

    def shutdown(self) -> None:
        self._worker.shutdown()
