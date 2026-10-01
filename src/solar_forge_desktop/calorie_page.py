"""Native Easy Calorie Tracker page."""

from datetime import date
from typing import Callable

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QBoxLayout,
    QDateEdit,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from solar_forge_desktop.calendar_widgets import CALENDAR_STYLE, SELECTOR_STYLE, style_calendar
from solar_forge_desktop.calorie import CalorieDay, CalorieService, FoodItem
from solar_forge_desktop.workers import BackgroundWorker

STYLE = """
QWidget#caloriePage, QWidget#calorieBody { background: #0a0712; }
QScrollArea#calorieScroll { background: #0a0712; border: none; }
QFrame#calorieCard { background: #1a1533; border: 1px solid #302943;
    border-radius: 16px; }
QFrame#calorieTableCard { background: #1a1533; border: 1px solid #302943;
    border-radius: 16px; }
QLabel#calorieTitle { color: #f3f4f6; font-size: 32px; font-weight: 700; }
QLabel#calorieHeading { color: #f3f4f6; font-size: 18px; font-weight: 700; }
QLabel#calorieText { color: #f3f4f6; font-size: 14px; }
QLabel#calorieMuted { color: #a1a1aa; }
QLabel#calorieStatus { color: #fb7185; }
QLabel#caloriePurple { color: #8b5cf6; font-size: 23px; font-weight: 700; }
QLabel#caloriePink { color: #ec4899; font-size: 23px; font-weight: 700; }
QLabel#calorieBlue { color: #38bdf8; font-size: 23px; font-weight: 700; }
QLabel#calorieRed { color: #fb7185; font-size: 23px; font-weight: 700; }
QLineEdit#calorieInput, QDateEdit#calorieDate { background: #211b30;
    color: #f3f4f6; border: 1px solid #302943; border-radius: 9px;
    padding: 10px 12px; }
QLineEdit#calorieInput:focus, QDateEdit#calorieDate:focus { border-color: #8b5cf6; }
QPushButton#caloriePrimary { color: white; border: none; border-radius: 9px;
    background: #8b5cf6; padding: 10px 14px; font-weight: 700; }
QPushButton#calorieSecondary { color: #f3f4f6; border: 1px solid #483a64;
    border-radius: 9px; background: #292143; padding: 6px 12px; }
QPushButton#calorieDanger { color: #fb7185; border: 1px solid #5b3048;
    border-radius: 8px; background: #3a1d39; padding: 6px 10px; }
QProgressBar#calorieProgress { background: #211b30; border: 1px solid #302943;
    border-radius: 8px; }
QProgressBar#calorieProgress::chunk { background: #8b5cf6; border-radius: 7px; }
QTableWidget#calorieTable { background: #1a1533; alternate-background-color: #211b30;
    color: #f3f4f6; border: none; gridline-color: #302943;
    selection-background-color: #302348; }
QTableWidget#calorieTable QHeaderView::section { background: #211b30;
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


def _card() -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("calorieCard")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(22, 20, 22, 20)
    layout.setSpacing(10)
    return frame, layout


class CaloriePage(QWidget):
    def __init__(self, service: CalorieService, profile_id: int):
        super().__init__()
        self.service = service
        self.profile_id = profile_id
        self._serial = 0
        self.setObjectName("caloriePage")
        self.setStyleSheet(STYLE)
        self._build()
        self._worker = BackgroundWorker(self, "solar-forge-calorie")
        self._worker.busy_changed.connect(self._set_busy)
        self._worker.failed.connect(self._show_error)

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setObjectName("calorieScroll")
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        body = QWidget()
        body.setObjectName("calorieBody")
        scroll.setWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(48, 36, 48, 40)
        layout.setSpacing(18)
        header = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.header = header
        intro = QVBoxLayout()
        intro.addWidget(_label("Easy Calorie Tracker", "calorieTitle"))
        intro.addWidget(_label(
            "Track daily food logs, set caloric targets, and monitor your nutrition balance.",
            "calorieMuted",
        ))
        header.addLayout(intro, 1)
        self.date_input = QDateEdit()
        self.date_input.setObjectName("calorieDate")
        self.date_input.setAccessibleName("Selected calorie date")
        self.date_input.setDisplayFormat("MMM d, yyyy")
        self.date_input.setDate(QDate.currentDate())
        self.date_input.setCalendarPopup(True)
        style_calendar(self.date_input.calendarWidget())
        header.addWidget(self.date_input, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header)
        self.status = _label("", "calorieStatus")
        self.status.setAccessibleName("Calorie status")
        layout.addWidget(self.status)
        self.summary = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.summary.setSpacing(16)
        self._build_summary()
        layout.addLayout(self.summary)
        progress_card, progress_box = _card()
        progress_header = QHBoxLayout()
        progress_title = _label("Daily Budget Progress", "calorieText")
        progress_title.setWordWrap(False)
        progress_header.addWidget(progress_title)
        progress_header.addStretch()
        self.progress_label = _label("0% Consumed", "caloriePurple")
        progress_header.addWidget(self.progress_label)
        progress_box.addLayout(progress_header)
        self.progress = QProgressBar()
        self.progress.setObjectName("calorieProgress")
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(16)
        progress_box.addWidget(self.progress)
        scale = QHBoxLayout()
        scale.addWidget(_label("0 kcal", "calorieMuted"))
        scale.addStretch()
        self.half_goal = _label("1,000 kcal (50%)", "calorieMuted")
        scale.addWidget(self.half_goal)
        scale.addStretch()
        self.full_goal = _label("Goal: 2,000 kcal", "calorieMuted")
        scale.addWidget(self.full_goal)
        progress_box.addLayout(scale)
        layout.addWidget(progress_card)
        self.columns = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.columns.setSpacing(24)
        self._build_food_form()
        self._build_food_list()
        layout.addLayout(self.columns)
        layout.addStretch()
        self.date_input.dateChanged.connect(self.refresh)
        self._apply_responsive()

    def _build_summary(self) -> None:
        goal_card, goal_box = _card()
        goal_box.addWidget(_label("DAILY CALORIE TARGET", "calorieMuted"))
        goal_row = QHBoxLayout()
        self.target_value = _label("2,000 kcal", "caloriePurple")
        goal_row.addWidget(self.target_value, 1)
        self.edit_goal_button = QPushButton("Edit")
        self.edit_goal_button.setObjectName("calorieSecondary")
        self.edit_goal_button.setAccessibleName("Edit daily calorie target")
        self.edit_goal_button.clicked.connect(self._toggle_goal_editor)
        goal_row.addWidget(self.edit_goal_button)
        goal_box.addLayout(goal_row)
        self.goal_editor = QWidget()
        editor_row = QHBoxLayout(self.goal_editor)
        editor_row.setContentsMargins(0, 0, 0, 0)
        self.goal_input = QLineEdit("2000")
        self.goal_input.setObjectName("calorieInput")
        self.goal_input.setAccessibleName("Daily calorie target")
        self.goal_input.returnPressed.connect(self.save_goal)
        editor_row.addWidget(self.goal_input, 1)
        self.save_goal_button = QPushButton("Save")
        self.save_goal_button.setObjectName("caloriePrimary")
        self.save_goal_button.clicked.connect(self.save_goal)
        editor_row.addWidget(self.save_goal_button)
        goal_box.addWidget(self.goal_editor)
        self.goal_editor.hide()
        self.goal_description = _label("Inherited from past setting", "calorieMuted")
        goal_box.addWidget(self.goal_description)
        self.summary.addWidget(goal_card, 1)
        consumed_card, consumed_box = _card()
        consumed_box.addWidget(_label("TOTAL CONSUMED", "calorieMuted"))
        self.consumed_value = _label("0 kcal", "caloriePink")
        consumed_box.addWidget(self.consumed_value)
        self.consumed_description = _label("Logged food intake for today", "calorieMuted")
        consumed_box.addWidget(self.consumed_description)
        self.summary.addWidget(consumed_card, 1)
        remaining_card, remaining_box = _card()
        remaining_box.addWidget(_label("CALORIES REMAINING", "calorieMuted"))
        self.remaining_value = _label("2,000 kcal", "calorieBlue")
        remaining_box.addWidget(self.remaining_value)
        self.remaining_description = _label("Under daily target limit", "calorieMuted")
        remaining_box.addWidget(self.remaining_description)
        self.summary.addWidget(remaining_card, 1)

    def _build_food_form(self) -> None:
        card, box = _card()
        box.addWidget(_label("Log Food Intake", "calorieHeading"))
        box.addWidget(_label("FOOD/DRINK NAME", "calorieMuted"))
        self.food_input = QLineEdit()
        self.food_input.setObjectName("calorieInput")
        self.food_input.setAccessibleName("Food or drink name")
        self.food_input.setPlaceholderText("e.g. Avocado Toast or Coffee")
        self.food_input.setMaxLength(100)
        box.addWidget(self.food_input)
        box.addWidget(_label("CALORIES (KCAL)", "calorieMuted"))
        self.calories_input = QLineEdit()
        self.calories_input.setObjectName("calorieInput")
        self.calories_input.setAccessibleName("Calories")
        self.calories_input.setPlaceholderText("e.g. 350")
        self.calories_input.returnPressed.connect(self.add_food)
        box.addWidget(self.calories_input)
        self.add_button = QPushButton("Log Food Item")
        self.add_button.setObjectName("caloriePrimary")
        self.add_button.clicked.connect(self.add_food)
        box.addWidget(self.add_button)
        self.columns.addWidget(card, 2, Qt.AlignmentFlag.AlignTop)

    def _build_food_list(self) -> None:
        listing = QVBoxLayout()
        self.list_heading = _label("Logged Foods (0)", "calorieHeading")
        listing.addWidget(self.list_heading)
        self.empty_card, empty_box = _card()
        empty_title = _label("No foods logged for this date.", "calorieText")
        empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_box.addWidget(empty_title)
        empty_hint = _label(
            "Enter what you ate on the left to start tracking your daily intake.",
            "calorieMuted",
        )
        empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_box.addWidget(empty_hint)
        listing.addWidget(self.empty_card)
        self.table = QTableWidget(0, 3)
        self.table.setObjectName("calorieTable")
        self.table.setAccessibleName("Logged foods")
        self.table.setHorizontalHeaderLabels(("Food/Drink", "Calories", "Actions"))
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in (1, 2):
            self.table.horizontalHeader().setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )
        self.table.verticalHeader().hide()
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setFixedHeight(90)
        self.table_card = QFrame()
        self.table_card.setObjectName("calorieTableCard")
        table_box = QVBoxLayout(self.table_card)
        table_box.setContentsMargins(8, 8, 8, 8)
        table_box.addWidget(self.table)
        listing.addWidget(self.table_card)
        self.table_card.hide()
        self.truncation = _label("", "calorieMuted")
        listing.addWidget(self.truncation)
        listing.addStretch()
        self.columns.addLayout(listing, 3)

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
        self.save_goal_button.setEnabled(not busy)

    def _show_error(self, error: Exception) -> None:
        self.status.setText(
            str(error) if isinstance(error, ValueError)
            else "The calorie entry could not be saved. Please try again."
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

    def _render(self, result: CalorieDay) -> None:
        self.target_value.setText(f"{result.target:,} kcal")
        if not self.goal_editor.isVisible():
            self.goal_input.setText(str(result.target))
        self.goal_description.setText(
            "Set specifically for this date" if result.has_custom_goal
            else "Inherited from past setting"
        )
        self.consumed_value.setText(f"{result.consumed:,} kcal")
        self.consumed_description.setText(
            f"Logged food intake for {result.date:%B} {result.date.day}, {result.date.year}"
        )
        self.remaining_value.setText(f"{result.remaining:,} kcal")
        self.remaining_value.setObjectName(
            "calorieBlue" if result.remaining >= 0 else "calorieRed"
        )
        self.remaining_value.style().unpolish(self.remaining_value)
        self.remaining_value.style().polish(self.remaining_value)
        self.remaining_description.setText(
            "Under daily target limit" if result.remaining >= 0 else "Over target limit!"
        )
        self.progress.setValue(result.progress_percent)
        self.progress_label.setText(f"{result.progress_percent}% Consumed")
        self.half_goal.setText(f"{result.target // 2:,} kcal (50%)")
        self.full_goal.setText(f"Goal: {result.target:,} kcal")
        self.list_heading.setText(f"Logged Foods ({result.total_logs})")
        self.empty_card.setVisible(result.total_logs == 0)
        self.table_card.setVisible(result.total_logs > 0)
        self.table.setRowCount(len(result.foods))
        self.table.setFixedHeight(min(400, 42 + 50 * len(result.foods)))
        for row, food in enumerate(result.foods):
            self.table.setRowHeight(row, 50)
            self.table.setItem(row, 0, QTableWidgetItem(food.food_name))
            self.table.setItem(row, 1, QTableWidgetItem(f"{food.calories:,} kcal"))
            delete = QPushButton("Delete")
            delete.setObjectName("calorieDanger")
            delete.setAccessibleName(f"Delete {food.food_name}")
            delete.clicked.connect(lambda _checked=False, item=food: self._confirm_delete(item))
            self.table.setCellWidget(row, 2, delete)
        self.truncation.setText(
            f"Showing the latest {len(result.foods)} of {result.total_logs} foods."
            if result.total_logs > len(result.foods) else ""
        )

    def _toggle_goal_editor(self) -> None:
        visible = not self.goal_editor.isVisible()
        self.goal_editor.setVisible(visible)
        self.target_value.setVisible(not visible)
        self.goal_description.setVisible(not visible)
        if visible:
            self.goal_input.setFocus()

    def save_goal(self) -> None:
        selected = self._selected_date()
        target = self.goal_input.text()
        self._run(
            lambda: self.service.set_goal(self.profile_id, selected, target),
            lambda _: self._after_goal(),
        )

    def _after_goal(self) -> None:
        self.goal_editor.hide()
        self.target_value.show()
        self.goal_description.show()
        self.status.setText("Daily calorie target updated successfully!")
        self.status.setStyleSheet("color: #10b981;")
        self.refresh()

    def add_food(self) -> None:
        selected = self._selected_date()
        name = self.food_input.text()
        calories = self.calories_input.text()
        self._run(
            lambda: self.service.add_food(self.profile_id, selected, name, calories),
            lambda _: self._after_food(name.strip(), calories.strip()),
        )

    def _after_food(self, name: str, calories: str) -> None:
        self.food_input.clear()
        self.calories_input.clear()
        self.status.setText(f"Logged '{name}' ({calories} kcal) successfully!")
        self.status.setStyleSheet("color: #10b981;")
        self.refresh()

    def _confirm_delete(self, food: FoodItem) -> None:
        dialog = QDialog(self)
        dialog.setObjectName("calorieDeleteDialog")
        dialog.setWindowTitle("Delete food log")
        dialog.setStyleSheet("""
            QDialog#calorieDeleteDialog { background: #1a1533; color: #f3f4f6; }
            QLabel { color: #f3f4f6; }
            QPushButton { background: #292143; color: #f3f4f6; padding: 10px 16px;
                border: 1px solid #483a64; border-radius: 9px; }
            QPushButton#calorieConfirmDelete { background: #be3153; border-color: #e44970; }
        """)
        box = QVBoxLayout(dialog)
        box.setContentsMargins(24, 24, 24, 24)
        box.addWidget(_label(
            f"Are you sure you want to remove '{food.food_name}'?", "calorieHeading"
        ))
        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton("Cancel")
        cancel.setDefault(True)
        cancel.clicked.connect(dialog.reject)
        buttons.addWidget(cancel)
        confirm = QPushButton("Delete food")
        confirm.setObjectName("calorieConfirmDelete")
        confirm.clicked.connect(dialog.accept)
        buttons.addWidget(confirm)
        box.addLayout(buttons)
        cancel.setFocus()
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        dialog.deleteLater()
        if accepted:
            self._run(
                lambda: self.service.delete_food(self.profile_id, food.id),
                lambda _: self._after_delete(food.food_name),
            )

    def _after_delete(self, name: str) -> None:
        self.status.setText(f"Removed '{name}'.")
        self.status.setStyleSheet("color: #10b981;")
        self.refresh()

    def shutdown(self) -> None:
        self._worker.shutdown()
