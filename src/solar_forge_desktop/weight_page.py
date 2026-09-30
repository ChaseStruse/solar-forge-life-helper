"""Native Weight Progression Tracker with an offline Qt trend chart."""

from datetime import date
from decimal import Decimal
from typing import Callable

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QBoxLayout,
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
    QVBoxLayout,
    QWidget,
)

from solar_forge_desktop.calendar_widgets import CALENDAR_STYLE, style_calendar
from solar_forge_desktop.weight import WeighInItem, WeightService, WeightView
from solar_forge_desktop.workers import BackgroundWorker

STYLE = """
QWidget#weightPage, QWidget#weightBody { background: #0a0712; }
QScrollArea#weightScroll { background: #0a0712; border: none; }
QFrame#weightCard { background: #1a1533; border: 1px solid #302943; border-radius: 16px; }
QLabel#weightTitle { color: #f3f4f6; font-size: 32px; font-weight: 700; }
QLabel#weightHeading { color: #f3f4f6; font-size: 18px; font-weight: 700; }
QLabel#weightText { color: #f3f4f6; font-size: 14px; }
QLabel#weightMuted { color: #a1a1aa; }
QLabel#weightStatus { color: #fb7185; }
QLabel#weightValue { color: #a1a1aa; font-size: 23px; font-weight: 700; }
QLabel#weightIndigo { color: #6366f1; font-size: 23px; font-weight: 700; }
QLabel#weightPurple { color: #8b5cf6; font-size: 23px; font-weight: 700; }
QLabel#weightGreen { color: #10b981; font-size: 23px; font-weight: 700; }
QLabel#weightRed { color: #fb7185; font-size: 23px; font-weight: 700; }
QLabel#weightBlue { color: #38bdf8; font-size: 23px; font-weight: 700; }
QLineEdit#weightInput, QDateEdit#weightDate { background: #211b30; color: #f3f4f6;
    border: 1px solid #302943; border-radius: 9px; padding: 10px 12px; }
QLineEdit#weightInput:focus, QDateEdit#weightDate:focus { border-color: #8b5cf6; }
QDateEdit::up-button, QDateEdit::down-button { background: #302943; width: 18px; }
QPushButton#weightPrimary { color: white; border: none; border-radius: 9px;
    background: #8b5cf6; padding: 10px 14px; font-weight: 700; }
QPushButton#weightSecondary { color: #f3f4f6; border: 1px solid #6366f1;
    border-radius: 9px; background: #292143; padding: 9px 13px; font-weight: 700; }
QPushButton#weightDanger { color: #fb7185; border: 1px solid #5b3048;
    border-radius: 8px; background: #3a1d39; padding: 6px 10px; }
QTableWidget#weightTable { background: #1a1533; alternate-background-color: #211b30;
    color: #f3f4f6; border: none; gridline-color: #302943;
    selection-background-color: #302348; }
QTableWidget#weightTable QHeaderView::section { background: #211b30;
    color: #a1a1aa; border: none; padding: 8px; font-weight: 700; }
QScrollBar:vertical { background: #151027; width: 10px; }
QScrollBar::handle:vertical { background: #483a64; border-radius: 5px; min-height: 28px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
""" + CALENDAR_STYLE


def _label(text: str, name: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName(name)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    return label


def _card() -> tuple[QFrame, QVBoxLayout]:
    card = QFrame()
    card.setObjectName("weightCard")
    box = QVBoxLayout(card)
    box.setContentsMargins(22, 20, 22, 20)
    box.setSpacing(10)
    return card, box


def _selected(field: QDateEdit) -> date:
    chosen = field.date()
    return date(chosen.year(), chosen.month(), chosen.day())


class WeightChart(QWidget):
    def __init__(self):
        super().__init__()
        self.points: tuple[tuple[date, Decimal], ...] = ()
        self.target: Decimal | None = None
        self.setObjectName("weightChart")
        self.setAccessibleName("Weight progression trend")
        self.setMinimumHeight(280)

    def set_data(
        self, points: tuple[tuple[date, Decimal], ...], target: Decimal | None
    ) -> None:
        self.points = points
        self.target = target
        self.setAccessibleDescription(
            ", ".join(f"{day.isoformat()}: {weight:.1f}" for day, weight in points)
        )
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        area = self.rect().adjusted(54, 15, -18, -37)
        if area.width() <= 0 or area.height() <= 0:
            return
        values = [float(weight) for _, weight in self.points]
        if self.target is not None:
            values.append(float(self.target))
        if not values:
            return
        low, high = min(values), max(values)
        padding = max((high - low) * 0.2, 1.0)
        low -= padding
        high += padding

        def y_position(value: float) -> float:
            return area.bottom() - (value - low) / (high - low) * area.height()

        painter.setPen(QPen(QColor("#302943"), 1))
        for step in range(5):
            y = area.top() + area.height() * step / 4
            painter.drawLine(area.left(), int(y), area.right(), int(y))
            painter.setPen(QColor("#a1a1aa"))
            painter.drawText(0, int(y) + 5, 48, 16,
                             Qt.AlignmentFlag.AlignRight, f"{high - (high-low)*step/4:.1f}")
            painter.setPen(QPen(QColor("#302943"), 1))
        if self.target is not None:
            y = int(y_position(float(self.target)))
            painter.setPen(QPen(QColor("#8b5cf6"), 1, Qt.PenStyle.DashLine))
            painter.drawLine(area.left(), y, area.right(), y)
        if not self.points:
            return
        chart = []
        count = len(self.points)
        for index, (_, weight) in enumerate(self.points):
            x = area.left() + area.width() * index / max(1, count - 1)
            chart.append((x, y_position(float(weight))))
        path = QPainterPath()
        path.moveTo(*chart[0])
        for point in chart[1:]:
            path.lineTo(*point)
        fill = QPainterPath(path)
        fill.lineTo(chart[-1][0], area.bottom())
        fill.lineTo(chart[0][0], area.bottom())
        fill.closeSubpath()
        gradient = QLinearGradient(0, area.top(), 0, area.bottom())
        gradient.setColorAt(0, QColor(99, 102, 241, 90))
        gradient.setColorAt(1, QColor(99, 102, 241, 2))
        painter.fillPath(fill, gradient)
        painter.setPen(QPen(QColor("#6366f1"), 3))
        painter.drawPath(path)
        painter.setPen(QPen(QColor("#ffffff"), 2))
        painter.setBrush(QColor("#8b5cf6"))
        for x, y in chart:
            painter.drawEllipse(int(x) - 5, int(y) - 5, 10, 10)
        painter.setPen(QColor("#a1a1aa"))
        for index in sorted({0, count // 2, count - 1}):
            x = chart[index][0]
            day = self.points[index][0]
            painter.drawText(int(x) - 38, area.bottom() + 8, 76, 24,
                             Qt.AlignmentFlag.AlignCenter, f"{day:%b} {day.day}")


class WeightPage(QWidget):
    def __init__(self, service: WeightService, profile_id: int):
        super().__init__()
        self.service = service
        self.profile_id = profile_id
        self._serial = 0
        self._goal = None
        self.setObjectName("weightPage")
        self.setStyleSheet(STYLE)
        self._build()
        self._worker = BackgroundWorker(self, "solar-forge-weight")
        self._worker.busy_changed.connect(self._set_busy)
        self._worker.failed.connect(self._show_error)

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setObjectName("weightScroll")
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        body = QWidget()
        body.setObjectName("weightBody")
        scroll.setWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(48, 36, 48, 40)
        layout.setSpacing(18)
        layout.addWidget(_label("Weight Progression Tracker", "weightTitle"))
        layout.addWidget(_label(
            "Track your weight milestones, log weigh-in entries, and visualize your "
            "progression trend.", "weightMuted"
        ))
        self.status = _label("", "weightStatus")
        self.status.setAccessibleName("Weight status")
        layout.addWidget(self.status)
        self.summary = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.summary.setSpacing(16)
        self._build_summary()
        layout.addLayout(self.summary)
        self.stats = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.stats.setSpacing(16)
        self._build_stats()
        layout.addLayout(self.stats)
        self.chart_card, chart_box = _card()
        chart_box.addWidget(_label("WEIGHT PROGRESSION TREND", "weightHeading"))
        self.chart = WeightChart()
        chart_box.addWidget(self.chart)
        layout.addWidget(self.chart_card)
        self.columns = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.columns.setSpacing(24)
        self._build_forms()
        self._build_history()
        layout.addLayout(self.columns)
        layout.addStretch()
        self._apply_responsive()

    def _summary_card(self, title: str, value_name: str) -> tuple[QLabel, QLabel, QVBoxLayout]:
        card, box = _card()
        box.addWidget(_label(title, "weightMuted"))
        value = _label("--", value_name)
        box.addWidget(value)
        desc = _label("", "weightMuted")
        box.addWidget(desc)
        self.summary.addWidget(card, 1)
        return value, desc, box

    def _build_summary(self) -> None:
        self.start_value, self.start_desc, _ = self._summary_card(
            "STARTING WEIGHT", "weightValue"
        )
        self.current_value, self.current_desc, _ = self._summary_card(
            "CURRENT WEIGHT", "weightIndigo"
        )
        target_card, box = _card()
        box.addWidget(_label("TARGET WEIGHT", "weightMuted"))
        target_row = QHBoxLayout()
        self.target_value = _label("--", "weightPurple")
        target_row.addWidget(self.target_value, 1)
        self.edit_target_button = QPushButton("Edit")
        self.edit_target_button.setObjectName("weightSecondary")
        self.edit_target_button.setAccessibleName("Edit target weight")
        self.edit_target_button.clicked.connect(self._toggle_target_editor)
        target_row.addWidget(self.edit_target_button)
        box.addLayout(target_row)
        self.target_desc = _label("", "weightMuted")
        box.addWidget(self.target_desc)
        self.target_editor = QWidget()
        target_row = QHBoxLayout(self.target_editor)
        target_row.setContentsMargins(0, 0, 0, 0)
        self.target_input = QLineEdit()
        self.target_input.setObjectName("weightInput")
        self.target_input.setAccessibleName("Target weight")
        target_row.addWidget(self.target_input)
        self.save_target_button = QPushButton("Save")
        self.save_target_button.setObjectName("weightPrimary")
        self.save_target_button.clicked.connect(self.save_target)
        target_row.addWidget(self.save_target_button)
        box.addWidget(self.target_editor)
        self.target_editor.hide()
        self.summary.addWidget(target_card, 1)

    def _build_stats(self) -> None:
        self.stat_cards = []
        for title, name, hint in (
            ("Total Milestones Delta", "weightGreen", "Change since starting weight"),
            ("Remaining to Target", "weightBlue", "Difference from target weight"),
            ("Goal Completion", "weightPurple", "Progression index"),
        ):
            card, box = _card()
            box.addWidget(_label(title, "weightMuted"))
            value = _label("--", name)
            box.addWidget(value)
            box.addWidget(_label(hint, "weightMuted"))
            self.stats.addWidget(card, 1)
            self.stat_cards.append((card, value))

    def _date_field(self, name: str, value: QDate) -> QDateEdit:
        field = QDateEdit()
        field.setObjectName("weightDate")
        field.setAccessibleName(name)
        field.setDisplayFormat("MMM d, yyyy")
        field.setDate(value)
        field.setCalendarPopup(True)
        style_calendar(field.calendarWidget())
        return field

    def _line(self, name: str, placeholder: str) -> QLineEdit:
        field = QLineEdit()
        field.setObjectName("weightInput")
        field.setAccessibleName(name)
        field.setPlaceholderText(placeholder)
        return field

    def _build_forms(self) -> None:
        form_column = QVBoxLayout()
        form_column.setSpacing(24)
        self.goal_card, goal_box = _card()
        goal_box.addWidget(_label("Goal Profile Settings", "weightHeading"))
        goal_box.addWidget(_label("START WEIGHT", "weightMuted"))
        self.start_input = self._line("Start weight", "e.g. 185.0")
        goal_box.addWidget(self.start_input)
        goal_box.addWidget(_label("START DATE", "weightMuted"))
        self.start_date = self._date_field("Start date", QDate.currentDate())
        goal_box.addWidget(self.start_date)
        goal_box.addWidget(_label("GOAL WEIGHT", "weightMuted"))
        self.goal_input = self._line("Goal weight", "e.g. 170.0")
        goal_box.addWidget(self.goal_input)
        goal_box.addWidget(_label("GOAL DATE", "weightMuted"))
        self.goal_date = self._date_field("Goal date", QDate.currentDate().addMonths(1))
        goal_box.addWidget(self.goal_date)
        self.save_goal_button = QPushButton("Save Goal Settings")
        self.save_goal_button.setObjectName("weightPrimary")
        self.save_goal_button.clicked.connect(self.save_goal)
        goal_box.addWidget(self.save_goal_button)
        form_column.addWidget(self.goal_card)
        log_card, log_box = _card()
        log_box.addWidget(_label("Log Weigh-In", "weightHeading"))
        log_box.addWidget(_label("WEIGHT", "weightMuted"))
        self.weight_input = self._line("Weigh-in weight", "e.g. 181.5")
        log_box.addWidget(self.weight_input)
        log_box.addWidget(_label("DATE OF WEIGH-IN", "weightMuted"))
        self.weigh_date = self._date_field("Date of weigh-in", QDate.currentDate())
        log_box.addWidget(self.weigh_date)
        self.log_button = QPushButton("Record Weight")
        self.log_button.setObjectName("weightSecondary")
        self.log_button.clicked.connect(self.log_weight)
        log_box.addWidget(self.log_button)
        form_column.addWidget(log_card)
        form_column.addStretch()
        self.columns.addLayout(form_column, 2)

    def _build_history(self) -> None:
        listing = QVBoxLayout()
        self.history_heading = _label("Weigh-In Logs (0)", "weightHeading")
        listing.addWidget(self.history_heading)
        self.empty_card, empty_box = _card()
        empty_box.addWidget(_label("No weigh-ins recorded yet.", "weightText"))
        empty_box.addWidget(_label(
            "Record your first weigh-in to see your progress here.", "weightMuted"
        ))
        listing.addWidget(self.empty_card)
        self.table_card, table_box = _card()
        table_box.setContentsMargins(8, 8, 8, 8)
        self.table = QTableWidget(0, 4)
        self.table.setObjectName("weightTable")
        self.table.setAccessibleName("Weigh-in logs")
        self.table.setHorizontalHeaderLabels((
            "Weigh-In Date", "Recorded Weight", "Trend Change", "Actions"
        ))
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in (1, 2, 3):
            self.table.horizontalHeader().setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )
        self.table.verticalHeader().hide()
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setFixedHeight(90)
        table_box.addWidget(self.table)
        listing.addWidget(self.table_card)
        self.table_card.hide()
        self.truncation = _label("", "weightMuted")
        listing.addWidget(self.truncation)
        listing.addStretch()
        self.columns.addLayout(listing, 3)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_responsive()

    def _apply_responsive(self) -> None:
        direction = (
            QBoxLayout.Direction.TopToBottom if self.width() < 900
            else QBoxLayout.Direction.LeftToRight
        )
        self.columns.setDirection(direction)
        self.summary.setDirection(
            QBoxLayout.Direction.TopToBottom if self.width() < 700
            else QBoxLayout.Direction.LeftToRight
        )
        self.stats.setDirection(
            QBoxLayout.Direction.TopToBottom if self.width() < 700
            else QBoxLayout.Direction.LeftToRight
        )

    def activate(self) -> None:
        self.refresh()

    def _run(self, action: Callable[[], object], done: Callable[[object], None]) -> None:
        self._worker.submit(action, done)

    def _set_busy(self, busy: bool) -> None:
        for button in (self.save_goal_button, self.save_target_button, self.log_button):
            button.setEnabled(not busy)

    def _show_error(self, error: Exception) -> None:
        self.status.setText(
            str(error) if isinstance(error, ValueError)
            else "The weight entry could not be saved. Please try again."
        )
        self.status.setStyleSheet("color: #fb7185;")

    def refresh(self) -> None:
        self._serial += 1
        serial = self._serial
        self._run(
            lambda: self.service.view(self.profile_id),
            lambda result: self._render(result) if serial == self._serial else None,
        )

    def _render(self, result: WeightView) -> None:
        self._goal = result.goal
        goal = result.goal
        self.start_value.setText(f"{goal.start_weight:.1f}" if goal else "--")
        self.start_desc.setText(
            f"Established on {goal.start_date:%B} {goal.start_date.day}, "
            f"{goal.start_date.year}" if goal else "Set weight goal to establish"
        )
        self.current_value.setText(
            f"{result.latest_weight:.1f}" if result.latest_weight is not None else "--"
        )
        self.current_desc.setText(
            f"Latest weigh-in on {result.latest_date:%B} {result.latest_date.day}, "
            f"{result.latest_date.year}" if result.total_logs else "No weigh-ins logged yet"
        )
        self.target_value.setText(f"{goal.target_weight:.1f}" if goal else "--")
        self.target_desc.setText(
            f"Goal target by {goal.target_date:%B} {goal.target_date.day}, "
            f"{goal.target_date.year}" if goal else "Set goal weight & date"
        )
        self.edit_target_button.setVisible(goal is not None)
        self.goal_card.setVisible(goal is None)
        self.chart_card.setVisible(goal is not None)
        for card, _ in self.stat_cards:
            card.setVisible(goal is not None)
        if goal:
            change = result.total_change
            self.stat_cards[0][1].setText(f"{change:+.1f}")
            improving = change <= 0 if result.is_losing else change >= 0
            delta_label = self.stat_cards[0][1]
            delta_label.setObjectName("weightGreen" if improving else "weightRed")
            delta_label.style().unpolish(delta_label)
            delta_label.style().polish(delta_label)
            self.stat_cards[1][1].setText(f"{result.remaining:.1f}")
            self.stat_cards[2][1].setText(f"{result.progress_percent}%")
            self.chart.set_data(result.chart_points, goal.target_weight)
            if not self.target_editor.isVisible():
                self.target_input.setText(str(goal.target_weight))
        self.history_heading.setText(f"Weigh-In Logs ({result.total_logs})")
        self.empty_card.setVisible(result.total_logs == 0)
        self.table_card.setVisible(result.total_logs > 0)
        self.table.setRowCount(len(result.logs))
        self.table.setFixedHeight(min(400, 42 + 50 * len(result.logs)))
        for row, entry in enumerate(result.logs):
            self.table.setRowHeight(row, 50)
            self.table.setItem(row, 0, QTableWidgetItem(entry.date.isoformat()))
            weight_cell = QTableWidgetItem(f"{entry.weight:.1f}")
            weight_cell.setForeground(QBrush(QColor("#6366f1")))
            self.table.setItem(row, 1, weight_cell)
            trend_cell = QTableWidgetItem(f"{entry.difference:+.1f}")
            if entry.difference:
                improving = entry.difference < 0 if result.is_losing else entry.difference > 0
                trend_cell.setForeground(QBrush(QColor(
                    "#10b981" if improving else "#fb7185"
                )))
            else:
                trend_cell.setForeground(QBrush(QColor("#a1a1aa")))
            self.table.setItem(row, 2, trend_cell)
            delete = QPushButton("Delete")
            delete.setObjectName("weightDanger")
            delete.setAccessibleName(f"Delete weigh-in for {entry.date.isoformat()}")
            delete.clicked.connect(lambda _checked=False, item=entry: self._confirm_delete(item))
            self.table.setCellWidget(row, 3, delete)
        self.truncation.setText(
            f"Showing the latest {len(result.logs)} of {result.total_logs} weigh-ins."
            if result.total_logs > len(result.logs) else ""
        )

    def _toggle_target_editor(self) -> None:
        visible = not self.target_editor.isVisible()
        self.target_editor.setVisible(visible)
        self.target_value.setVisible(not visible)
        self.target_desc.setVisible(not visible)
        if visible:
            self.target_input.setFocus()

    def save_goal(self) -> None:
        start, target = self.start_input.text(), self.goal_input.text()
        start_date, target_date = _selected(self.start_date), _selected(self.goal_date)
        self._run(
            lambda: self.service.set_goal(
                self.profile_id, start, start_date, target, target_date
            ),
            lambda _: self._success("Weight goal profile updated successfully!"),
        )

    def save_target(self) -> None:
        goal = self._goal
        if goal is None:
            return
        target = self.target_input.text()
        self._run(
            lambda: self.service.set_goal(
                self.profile_id, str(goal.start_weight), goal.start_date,
                target, goal.target_date,
            ),
            lambda _: self._after_target(),
        )

    def _after_target(self) -> None:
        self.target_editor.hide()
        self.target_value.show()
        self.target_desc.show()
        self._success("Weight goal profile updated successfully!")

    def log_weight(self) -> None:
        selected = _selected(self.weigh_date)
        raw = self.weight_input.text()
        self._run(
            lambda: self.service.log(self.profile_id, selected, raw),
            lambda result: self._after_log(selected, raw, result[1]),
        )

    def _after_log(self, selected: date, raw: str, updated: bool) -> None:
        self.weight_input.clear()
        if updated:
            message = (
                f"Updated weigh-in for {selected:%B} {selected.day}, "
                f"{selected.year} to {raw}."
            )
        else:
            message = f"Logged weigh-in of {raw} successfully!"
        self._success(message)

    def _success(self, message: str) -> None:
        self.status.setText(message)
        self.status.setStyleSheet("color: #10b981;")
        self.refresh()

    def _confirm_delete(self, entry: WeighInItem) -> None:
        dialog = QDialog(self)
        dialog.setObjectName("weightDeleteDialog")
        dialog.setWindowTitle("Delete weigh-in")
        dialog.setStyleSheet("""
            QDialog#weightDeleteDialog { background: #1a1533; color: #f3f4f6; }
            QLabel { color: #f3f4f6; }
            QPushButton { background: #292143; color: #f3f4f6; padding: 10px 16px;
                border: 1px solid #483a64; border-radius: 9px; }
            QPushButton#weightConfirmDelete { background: #be3153; border-color: #e44970; }
        """)
        box = QVBoxLayout(dialog)
        box.setContentsMargins(24, 24, 24, 24)
        box.addWidget(_label(
            f"Remove the weigh-in for {entry.date:%B} {entry.date.day}, {entry.date.year}?",
            "weightHeading",
        ))
        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton("Cancel")
        cancel.setDefault(True)
        cancel.clicked.connect(dialog.reject)
        buttons.addWidget(cancel)
        confirm = QPushButton("Delete weigh-in")
        confirm.setObjectName("weightConfirmDelete")
        confirm.clicked.connect(dialog.accept)
        buttons.addWidget(confirm)
        box.addLayout(buttons)
        cancel.setFocus()
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        dialog.deleteLater()
        if accepted:
            self._run(
                lambda: self.service.delete(self.profile_id, entry.id),
                lambda _: self._success(
                    f"Deleted weigh-in for {entry.date:%B} "
                    f"{entry.date.day}, {entry.date.year}."
                ),
            )

    def shutdown(self) -> None:
        self._worker.shutdown()
