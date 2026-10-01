"""Native workout tracker page matching the web dashboard layout."""

from datetime import date
from typing import Callable

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QBoxLayout,
    QCheckBox,
    QDateEdit,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from solar_forge_desktop.calendar_widgets import CALENDAR_STYLE, SELECTOR_STYLE, style_calendar
from solar_forge_desktop.workers import BackgroundWorker
from solar_forge_desktop.workout import WorkoutDay, WorkoutItem, WorkoutService

STYLE = """
QWidget#workoutPage, QWidget#workoutBody { background: #0a0712; }
QScrollArea#workoutScroll { background: #0a0712; border: none; }
QFrame#workoutCard, QFrame#workoutTableCard { background: #1a1533;
    border: 1px solid #302943; border-radius: 16px; }
QLabel#workoutTitle { color: #f3f4f6; font-size: 32px; font-weight: 700; }
QLabel#workoutHeading { color: #f3f4f6; font-size: 18px; font-weight: 700; }
QLabel#workoutText { color: #f3f4f6; font-size: 14px; }
QLabel#workoutMuted { color: #a1a1aa; }
QLabel#workoutStatus { color: #fb7185; }
QLabel#workoutPurple { color: #8b5cf6; font-size: 23px; font-weight: 700; }
QLabel#workoutPink { color: #ec4899; font-size: 23px; font-weight: 700; }
QLabel#workoutBlue { color: #38bdf8; font-size: 23px; font-weight: 700; }
QLineEdit#workoutInput, QDateEdit#workoutDate, QTextEdit#workoutNotes {
    background: #211b30; color: #f3f4f6; border: 1px solid #302943;
    border-radius: 9px; padding: 10px 12px; }
QLineEdit#workoutInput:focus, QDateEdit#workoutDate:focus,
QTextEdit#workoutNotes:focus { border-color: #8b5cf6; }
QPushButton#workoutPrimary { color: white; border: none; border-radius: 9px;
    background: #8b5cf6; padding: 10px 14px; font-weight: 700; }
QPushButton#workoutSecondary { color: #f3f4f6; border: 1px solid #483a64;
    border-radius: 9px; background: #292143; padding: 6px 12px; }
QPushButton#workoutDanger { color: #fb7185; border: 1px solid #5b3048;
    border-radius: 8px; background: #3a1d39; padding: 6px 10px; }
QCheckBox#workoutCheckbox { color: #a1a1aa; spacing: 9px; }
QCheckBox#workoutCheckbox::indicator { width: 19px; height: 19px;
    border-radius: 5px; border: 1px solid #6f588e; background: #211b30; }
QCheckBox#workoutCheckbox::indicator:checked { background: #8b5cf6;
    border-color: #8b5cf6; }
QTableWidget#workoutTable { background: #1a1533;
    alternate-background-color: #211b30; color: #f3f4f6; border: none;
    gridline-color: #302943; selection-background-color: #302348; }
QTableWidget#workoutTable QHeaderView::section { background: #211b30;
    color: #a1a1aa; border: none; padding: 8px; font-weight: 700; }
QScrollBar:vertical { background: #151027; width: 10px; }
QScrollBar::handle:vertical { background: #483a64; border-radius: 5px; min-height: 28px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
""" + CALENDAR_STYLE + SELECTOR_STYLE


def _label(text: str, name: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName(name)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    return label


def _card(name: str = "workoutCard") -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName(name)
    box = QVBoxLayout(frame)
    box.setContentsMargins(22, 20, 22, 20)
    box.setSpacing(10)
    return frame, box


def _input(accessible: str, placeholder: str = "") -> QLineEdit:
    field = QLineEdit()
    field.setObjectName("workoutInput")
    field.setAccessibleName(accessible)
    field.setPlaceholderText(placeholder)
    return field


class WorkoutPage(QWidget):
    def __init__(self, service: WorkoutService, profile_id: int):
        super().__init__()
        self.service = service
        self.profile_id = profile_id
        self._serial = 0
        self._editing_id: int | None = None
        self.setObjectName("workoutPage")
        self.setStyleSheet(STYLE)
        self._build()
        self._worker = BackgroundWorker(self, "solar-forge-workout")
        self._worker.busy_changed.connect(self._set_busy)
        self._worker.failed.connect(self._show_error)

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setObjectName("workoutScroll")
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        body = QWidget()
        body.setObjectName("workoutBody")
        scroll.setWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(48, 36, 48, 40)
        layout.setSpacing(18)
        self.header = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        intro = QVBoxLayout()
        intro.addWidget(_label("Easy Workout Tracker", "workoutTitle"))
        intro.addWidget(_label(
            "Log exercises by day — track sets, reps, and weight for every workout.",
            "workoutMuted",
        ))
        self.header.addLayout(intro, 1)
        date_row = QHBoxLayout()
        self.previous_button = QPushButton("‹")
        self.previous_button.setObjectName("workoutSecondary")
        self.previous_button.setAccessibleName("Previous day")
        self.previous_button.clicked.connect(lambda: self.date_input.setDate(
            self.date_input.date().addDays(-1)
        ))
        date_row.addWidget(self.previous_button)
        self.date_input = QDateEdit()
        self.date_input.setObjectName("workoutDate")
        self.date_input.setAccessibleName("Selected workout date")
        self.date_input.setDisplayFormat("MMM d, yyyy")
        self.date_input.setDate(QDate.currentDate())
        self.date_input.setCalendarPopup(True)
        style_calendar(self.date_input.calendarWidget())
        date_row.addWidget(self.date_input)
        self.next_button = QPushButton("›")
        self.next_button.setObjectName("workoutSecondary")
        self.next_button.setAccessibleName("Next day")
        self.next_button.clicked.connect(lambda: self.date_input.setDate(
            self.date_input.date().addDays(1)
        ))
        date_row.addWidget(self.next_button)
        self.header.addLayout(date_row)
        layout.addLayout(self.header)
        self.status = _label("", "workoutStatus")
        self.status.setAccessibleName("Workout status")
        layout.addWidget(self.status)
        self.summary = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.summary.setSpacing(16)
        for title, name, description, attribute in (
            ("EXERCISES LOGGED", "workoutPurple", "", "exercise_value"),
            ("TOTAL SETS", "workoutPink", "Across all exercises today", "sets_value"),
            ("TOTAL REPS", "workoutBlue", "Total repetitions performed", "reps_value"),
        ):
            card, box = _card()
            box.addWidget(_label(title, "workoutMuted"))
            value = _label("0", name)
            setattr(self, attribute, value)
            box.addWidget(value)
            desc = _label(description, "workoutMuted")
            if attribute == "exercise_value":
                self.day_description = desc
            box.addWidget(desc)
            self.summary.addWidget(card, 1)
        layout.addLayout(self.summary)
        self.columns = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.columns.setSpacing(24)
        self._build_form()
        self._build_list()
        layout.addLayout(self.columns)
        layout.addStretch()
        self.date_input.dateChanged.connect(self.refresh)
        self._apply_responsive()

    def _build_form(self) -> None:
        card, box = _card()
        box.addWidget(_label("Log Exercise", "workoutHeading"))
        box.addWidget(_label("EXERCISE NAME", "workoutMuted"))
        self.name_input = _input("Exercise name", "e.g. Push-ups, Bench Press")
        self.name_input.setMaxLength(150)
        box.addWidget(self.name_input)
        numbers = QHBoxLayout()
        for label, attribute, placeholder in (
            ("SETS", "sets_input", "3"), ("REPS", "reps_input", "10")
        ):
            group = QVBoxLayout()
            group.addWidget(_label(label, "workoutMuted"))
            field = _input(label.title(), placeholder)
            setattr(self, attribute, field)
            group.addWidget(field)
            numbers.addLayout(group, 1)
        box.addLayout(numbers)
        self.bodyweight = QCheckBox("Bodyweight Exercise")
        self.bodyweight.setObjectName("workoutCheckbox")
        self.bodyweight.setAccessibleName("Bodyweight exercise")
        self.bodyweight.toggled.connect(self._toggle_weight)
        box.addWidget(self.bodyweight)
        self.weight_group = QWidget()
        weight_box = QVBoxLayout(self.weight_group)
        weight_box.setContentsMargins(0, 0, 0, 0)
        weight_box.addWidget(_label("WEIGHT (LBS) — OPTIONAL", "workoutMuted"))
        self.weight_input = _input("Weight in pounds", "e.g. 135")
        weight_box.addWidget(self.weight_input)
        box.addWidget(self.weight_group)
        box.addWidget(_label("NOTES — OPTIONAL", "workoutMuted"))
        self.notes_input = QTextEdit()
        self.notes_input.setObjectName("workoutNotes")
        self.notes_input.setAccessibleName("Exercise notes")
        self.notes_input.setPlaceholderText("e.g. felt strong, increased weight")
        self.notes_input.setFixedHeight(80)
        box.addWidget(self.notes_input)
        self.add_button = QPushButton("Log Exercise")
        self.add_button.setObjectName("workoutPrimary")
        self.add_button.clicked.connect(self.add_exercise)
        box.addWidget(self.add_button)
        self.columns.addWidget(card, 11, Qt.AlignmentFlag.AlignTop)

    def _build_list(self) -> None:
        listing = QVBoxLayout()
        self.list_heading = _label("Today's Exercises (0)", "workoutHeading")
        listing.addWidget(self.list_heading)
        self.empty_card, empty_box = _card()
        self.empty_title = _label("No exercises logged for this date.", "workoutText")
        self.empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_box.addWidget(self.empty_title)
        hint = _label("Use the form to log your first exercise.", "workoutMuted")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_box.addWidget(hint)
        listing.addWidget(self.empty_card)
        self.table = QTableWidget(0, 5)
        self.table.setObjectName("workoutTable")
        self.table.setAccessibleName("Logged exercises")
        self.table.setHorizontalHeaderLabels(("Exercise", "Sets", "Reps", "Weight", "Actions"))
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in (1, 2, 3, 4):
            self.table.horizontalHeader().setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )
        self.table.verticalHeader().hide()
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setFixedHeight(90)
        self.table_card, table_box = _card("workoutTableCard")
        table_box.setContentsMargins(8, 8, 8, 8)
        table_box.addWidget(self.table)
        listing.addWidget(self.table_card)
        self.table_card.hide()
        self.truncation = _label("", "workoutMuted")
        listing.addWidget(self.truncation)
        listing.addStretch()
        self.columns.addLayout(listing, 19)

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
        self.columns.setDirection(
            QBoxLayout.Direction.TopToBottom if self.width() < 900
            else QBoxLayout.Direction.LeftToRight
        )

    def activate(self) -> None:
        self.refresh()

    def _selected_date(self) -> date:
        selected = self.date_input.date()
        return date(selected.year(), selected.month(), selected.day())

    def _run(self, action: Callable[[], object], done: Callable[[object], None]) -> None:
        self._worker.submit(action, done)

    def _set_busy(self, busy: bool) -> None:
        self.add_button.setEnabled(not busy)
        self.table.setEnabled(not busy)

    def _show_error(self, error: Exception) -> None:
        self.status.setText(
            str(error) if isinstance(error, ValueError)
            else "The exercise could not be saved. Please try again."
        )
        self.status.setStyleSheet("color: #fb7185;")

    def refresh(self) -> None:
        self._serial += 1
        serial = self._serial
        selected = self._selected_date()
        self._run(
            lambda: self.service.view(self.profile_id, selected),
            lambda result: self._render(result) if serial == self._serial else None,
        )

    def _render(self, result: WorkoutDay) -> None:
        self.exercise_value.setText(str(result.exercise_count))
        self.sets_value.setText(str(result.total_sets))
        self.reps_value.setText(str(result.total_reps))
        display = f"{result.date:%B} {result.date.day}, {result.date.year}"
        self.day_description.setText(display)
        self.list_heading.setText(f"Today's Exercises ({result.exercise_count})")
        self.empty_title.setText(f"No exercises logged for {display}.")
        self.empty_card.setVisible(result.exercise_count == 0)
        self.table_card.setVisible(result.exercise_count > 0)
        self._editing_id = None
        self._items = result.exercises
        self.table.clearSpans()
        self.table.clearContents()
        self.table.setRowCount(len(result.exercises))
        self.table.setFixedHeight(min(480, 42 + 62 * len(result.exercises)))
        for row, item in enumerate(result.exercises):
            self.table.setRowHeight(row, 62)
            name = item.exercise_name + (f"\n{item.notes}" if item.notes else "")
            self.table.setItem(row, 0, QTableWidgetItem(name))
            self.table.setItem(row, 1, QTableWidgetItem(str(item.sets)))
            self.table.setItem(row, 2, QTableWidgetItem(str(item.reps)))
            weight = "Bodyweight" if item.is_bodyweight else (
                f"{item.weight_lbs} lbs" if item.weight_lbs is not None else "—"
            )
            self.table.setItem(row, 3, QTableWidgetItem(weight))
            actions = QWidget()
            action_box = QHBoxLayout(actions)
            action_box.setContentsMargins(2, 2, 2, 2)
            action_box.setSpacing(4)
            edit = QPushButton("Edit")
            edit.setObjectName("workoutSecondary")
            edit.setAccessibleName(f"Edit {item.exercise_name}")
            edit.clicked.connect(lambda _checked=False, entry=item: self._start_edit(entry))
            action_box.addWidget(edit)
            delete = QPushButton("Delete")
            delete.setObjectName("workoutDanger")
            delete.setAccessibleName(f"Delete {item.exercise_name}")
            delete.clicked.connect(lambda _checked=False, entry=item: self._confirm_delete(entry))
            action_box.addWidget(delete)
            self.table.setCellWidget(row, 4, actions)
        self.truncation.setText(
            f"Showing the latest {len(result.exercises)} of {result.exercise_count} exercises."
            if result.exercise_count > len(result.exercises) else ""
        )

    def _toggle_weight(self, checked: bool) -> None:
        self.weight_group.setVisible(not checked)
        if checked:
            self.weight_input.clear()

    @staticmethod
    def _whole_number(raw: str, label: str) -> int:
        try:
            return int(raw.strip())
        except ValueError as exc:
            raise ValueError(f"{label} must be a whole number.") from exc

    def add_exercise(self) -> None:
        try:
            sets = self._whole_number(self.sets_input.text(), "Sets")
            reps = self._whole_number(self.reps_input.text(), "Reps")
        except ValueError as error:
            self._show_error(error)
            return
        name = self.name_input.text()
        weight = self.weight_input.text()
        bodyweight = self.bodyweight.isChecked()
        notes = self.notes_input.toPlainText()
        selected = self._selected_date()
        self._run(
            lambda: self.service.add(
                self.profile_id, selected, name, sets, reps, bodyweight, weight, notes
            ),
            lambda _: self._after_add(name.strip(), sets, reps, bodyweight, weight),
        )

    def _after_add(self, name: str, sets: int, reps: int, bodyweight: bool, weight: str) -> None:
        self.name_input.clear()
        self.sets_input.clear()
        self.reps_input.clear()
        self.bodyweight.setChecked(False)
        self.weight_input.clear()
        self.notes_input.clear()
        suffix = "Bodyweight" if bodyweight else (
            f"{weight.strip()} lbs" if weight.strip() else "No weight"
        )
        self.status.setText(f"Logged '{name}' — {sets}×{reps} @ {suffix}.")
        self.status.setStyleSheet("color: #10b981;")
        self.refresh()

    def _start_edit(self, item: WorkoutItem) -> None:
        if self._editing_id is not None:
            return
        row = next((index for index, entry in enumerate(self._items)
                    if entry.id == item.id), None)
        if row is None:
            return
        self._editing_id = item.id
        self.table.setSpan(row, 0, 1, 5)
        editor = QWidget()
        editor.setObjectName("workoutInlineEditor")
        box = QVBoxLayout(editor)
        box.setContentsMargins(8, 6, 8, 6)
        fields = QHBoxLayout()
        name = _input("Edit exercise name")
        name.setText(item.exercise_name)
        fields.addWidget(name, 3)
        sets = _input("Edit sets")
        sets.setText(str(item.sets))
        fields.addWidget(sets, 1)
        reps = _input("Edit reps")
        reps.setText(str(item.reps))
        fields.addWidget(reps, 1)
        weight = _input("Edit weight in pounds", "Weight (lbs)")
        weight.setText(str(item.weight_lbs) if item.weight_lbs is not None else "")
        weight.setVisible(not item.is_bodyweight)
        fields.addWidget(weight, 2)
        bodyweight = QCheckBox("Bodyweight")
        bodyweight.setObjectName("workoutCheckbox")
        bodyweight.setChecked(item.is_bodyweight)
        fields.addWidget(bodyweight)
        box.addLayout(fields)

        def toggle_edit_weight(checked: bool) -> None:
            weight.setVisible(not checked)
            if checked:
                weight.clear()

        bodyweight.toggled.connect(toggle_edit_weight)
        buttons = QHBoxLayout()
        buttons.addStretch()
        save = QPushButton("Save")
        save.setObjectName("workoutPrimary")
        buttons.addWidget(save)
        cancel = QPushButton("Cancel")
        cancel.setObjectName("workoutSecondary")
        cancel.clicked.connect(self.refresh)
        buttons.addWidget(cancel)
        box.addLayout(buttons)

        def submit() -> None:
            try:
                parsed_sets = self._whole_number(sets.text(), "Sets")
                parsed_reps = self._whole_number(reps.text(), "Reps")
            except ValueError as error:
                self._show_error(error)
                return
            values = (name.text(), parsed_sets, parsed_reps, bodyweight.isChecked(),
                      weight.text(), item.notes)
            self._run(
                lambda: self.service.edit(self.profile_id, item.id, *values),
                lambda _: self._after_edit(values[0].strip()),
            )

        save.clicked.connect(submit)
        self.table.setCellWidget(row, 0, editor)
        self.table.setRowHeight(row, 108)
        self.table.setFixedHeight(min(480, 42 + 62 * len(self._items) + 46))

    def _after_edit(self, name: str) -> None:
        self.status.setText(f"Updated '{name}' successfully.")
        self.status.setStyleSheet("color: #10b981;")
        self.refresh()

    def _confirm_delete(self, item: WorkoutItem) -> None:
        dialog = QDialog(self)
        dialog.setObjectName("workoutDeleteDialog")
        dialog.setWindowTitle("Delete exercise")
        dialog.setStyleSheet(STYLE + "QDialog#workoutDeleteDialog { background: #1a1533; }")
        box = QVBoxLayout(dialog)
        box.setContentsMargins(24, 24, 24, 24)
        box.addWidget(_label(
            f"Are you sure you want to remove '{item.exercise_name}'?", "workoutHeading"
        ))
        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton("Cancel")
        cancel.setObjectName("workoutSecondary")
        cancel.setDefault(True)
        cancel.clicked.connect(dialog.reject)
        buttons.addWidget(cancel)
        confirm = QPushButton("Delete exercise")
        confirm.setObjectName("workoutDanger")
        confirm.clicked.connect(dialog.accept)
        buttons.addWidget(confirm)
        box.addLayout(buttons)
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        dialog.deleteLater()
        if accepted:
            self._run(
                lambda: self.service.delete(self.profile_id, item.id),
                lambda _: self._after_delete(item.exercise_name),
            )

    def _after_delete(self, name: str) -> None:
        self.status.setText(f"Removed '{name}'.")
        self.status.setStyleSheet("color: #10b981;")
        self.refresh()

    def shutdown(self) -> None:
        self._worker.shutdown()
