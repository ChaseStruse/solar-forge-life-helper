"""Native Home Maintenance schedule and recurring item form."""

from datetime import date

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QBoxLayout,
    QComboBox,
    QDateEdit,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from solar_forge_desktop.calendar_widgets import CALENDAR_STYLE, style_calendar
from solar_forge_desktop.maintenance import (
    CATEGORIES,
    UNITS,
    MaintenanceEntry,
    MaintenanceService,
    MaintenanceView,
)
from solar_forge_desktop.workers import BackgroundWorker

STYLE = """
QWidget#maintenancePage, QWidget#maintenanceBody { background: #0a0712; }
QScrollArea#maintenanceScroll { background: #0a0712; border: none; }
QFrame#maintenanceCard { background: #1a1533; border: 1px solid #302943;
    border-radius: 16px; }
QFrame#maintenanceOverdue { background: #1a1533; border: 1px solid #302943;
    border-left: 3px solid #fb7185; border-radius: 16px; }
QFrame#maintenanceSoon { background: #1a1533; border: 1px solid #302943;
    border-left: 3px solid #38bdf8; border-radius: 16px; }
QFrame#maintenanceUpcoming { background: #1a1533; border: 1px solid #302943;
    border-left: 3px solid #8b5cf6; border-radius: 16px; }
QLabel#maintenanceEyebrow { color: #ec4899; font-size: 11px; font-weight: 700; }
QLabel#maintenanceTitle { color: #f3f4f6; font-size: 32px; font-weight: 700; }
QLabel#maintenanceHeading { color: #f3f4f6; font-size: 19px; font-weight: 700; }
QLabel#maintenanceText { color: #f3f4f6; font-size: 14px; }
QLabel#maintenanceMuted { color: #a1a1aa; }
QLabel#maintenanceStatus { color: #fb7185; }
QLabel#maintenancePurple { color: #8b5cf6; font-size: 23px; font-weight: 700; }
QLabel#maintenanceRed { color: #fb7185; font-size: 23px; font-weight: 700; }
QLabel#maintenanceBlue { color: #38bdf8; font-size: 23px; font-weight: 700; }
QLineEdit#maintenanceInput, QTextEdit#maintenanceNotes,
QDateEdit#maintenanceDate, QComboBox#maintenanceSelect { background: #211b30;
    color: #f3f4f6; border: 1px solid #302943; border-radius: 9px;
    padding: 9px 11px; }
QComboBox#maintenanceSelect QAbstractItemView { background: #211b30;
    color: #f3f4f6; }
QDateEdit::up-button, QDateEdit::down-button { background: #302943; width: 18px; }
QPushButton#maintenancePrimary { background: #8b5cf6; color: white; border: none;
    border-radius: 9px; padding: 10px 14px; font-weight: 700; }
QPushButton#maintenanceDanger { background: #3a1d39; color: #fb7185;
    border: 1px solid #5b3048; border-radius: 9px; padding: 8px 12px; }
QPushButton#maintenanceSecondary { background: #292143; color: #f3f4f6;
    border: 1px solid #483a64; border-radius: 9px; padding: 8px 12px; }
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


def _card(name: str = "maintenanceCard") -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName(name)
    box = QVBoxLayout(frame)
    box.setContentsMargins(22, 20, 22, 20)
    box.setSpacing(10)
    return frame, box


def _input(accessible: str, placeholder: str = "") -> QLineEdit:
    field = QLineEdit()
    field.setObjectName("maintenanceInput")
    field.setAccessibleName(accessible)
    field.setPlaceholderText(placeholder)
    return field


def _clear(layout: QVBoxLayout) -> None:
    while layout.count():
        part = layout.takeAt(0)
        if widget := part.widget():
            widget.deleteLater()


class MaintenancePage(QWidget):
    def __init__(self, service: MaintenanceService, profile_id: int):
        super().__init__()
        self.service = service
        self.profile_id = profile_id
        self._serial = 0
        self.setObjectName("maintenancePage")
        self.setStyleSheet(STYLE)
        self._build()
        self._worker = BackgroundWorker(self, "solar-forge-maintenance")
        self._worker.busy_changed.connect(self._set_busy)
        self._worker.failed.connect(self._show_error)

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setObjectName("maintenanceScroll")
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        body = QWidget()
        body.setObjectName("maintenanceBody")
        scroll.setWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(48, 36, 48, 40)
        layout.setSpacing(18)
        layout.addWidget(_label("YOUR HOME", "maintenanceEyebrow"))
        layout.addWidget(_label("Home Maintenance", "maintenanceTitle"))
        layout.addWidget(_label(
            "Keep recurring household care simple and visible.", "maintenanceMuted"
        ))
        self.status = _label("", "maintenanceStatus")
        self.status.setAccessibleName("Maintenance status")
        layout.addWidget(self.status)
        self.status.hide()
        self.summary = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.summary.setSpacing(16)
        for title, description, color, attribute in (
            ("TRACKED", "Recurring home tasks", "maintenancePurple", "tracked_value"),
            ("OVERDUE", "Needs attention", "maintenanceRed", "overdue_value"),
            ("DUE SOON", "Within 14 days", "maintenanceBlue", "soon_value"),
        ):
            card, box = _card()
            box.addWidget(_label(title, "maintenanceMuted"))
            value = _label("0", color)
            setattr(self, attribute, value)
            box.addWidget(value)
            box.addWidget(_label(description, "maintenanceMuted"))
            self.summary.addWidget(card, 1)
        layout.addLayout(self.summary)
        self.columns = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.columns.setSpacing(24)
        self._build_form()
        self._build_schedule()
        layout.addLayout(self.columns)
        layout.addStretch()
        self._apply_responsive()

    def _build_form(self) -> None:
        self.form_card, box = _card()
        box.addWidget(_label("Add Maintenance", "maintenanceHeading"))
        box.addWidget(_label("WHAT NEEDS CARE?", "maintenanceMuted"))
        self.name_input = _input("Maintenance item name", "Replace HVAC filter")
        self.name_input.setMaxLength(150)
        box.addWidget(self.name_input)
        box.addWidget(_label("CATEGORY", "maintenanceMuted"))
        self.category_input = QComboBox()
        self.category_input.setObjectName("maintenanceSelect")
        self.category_input.setAccessibleName("Maintenance category")
        self.category_input.addItems(CATEGORIES)
        box.addWidget(self.category_input)
        box.addWidget(_label("NEXT DUE", "maintenanceMuted"))
        self.due_input = QDateEdit()
        self.due_input.setObjectName("maintenanceDate")
        self.due_input.setAccessibleName("Next due date")
        self.due_input.setDisplayFormat("MMM d, yyyy")
        self.due_input.setDate(QDate.currentDate())
        self.due_input.setCalendarPopup(True)
        style_calendar(self.due_input.calendarWidget())
        box.addWidget(self.due_input)
        box.addWidget(_label("REPEAT EVERY", "maintenanceMuted"))
        repeat = QHBoxLayout()
        self.interval_input = _input("Repeat interval")
        self.interval_input.setText("1")
        repeat.addWidget(self.interval_input, 1)
        self.unit_input = QComboBox()
        self.unit_input.setObjectName("maintenanceSelect")
        self.unit_input.setAccessibleName("Repeat unit")
        for unit in UNITS:
            self.unit_input.addItem(unit.title(), unit)
        self.unit_input.setCurrentIndex(2)
        repeat.addWidget(self.unit_input, 2)
        box.addLayout(repeat)
        box.addWidget(_label("ESTIMATED COST — OPTIONAL", "maintenanceMuted"))
        self.cost_input = _input("Estimated cost", "0.00")
        box.addWidget(self.cost_input)
        box.addWidget(_label("NOTES — OPTIONAL", "maintenanceMuted"))
        self.notes_input = QTextEdit()
        self.notes_input.setObjectName("maintenanceNotes")
        self.notes_input.setAccessibleName("Maintenance notes")
        self.notes_input.setPlaceholderText("Size, part number, or helpful details")
        self.notes_input.setFixedHeight(80)
        box.addWidget(self.notes_input)
        self.add_button = QPushButton("Add Item")
        self.add_button.setObjectName("maintenancePrimary")
        self.add_button.clicked.connect(self.add_item)
        box.addWidget(self.add_button)
        self.columns.addWidget(self.form_card, 85, Qt.AlignmentFlag.AlignTop)

    def _build_schedule(self) -> None:
        listing = QVBoxLayout()
        heading = QHBoxLayout()
        title = _label("Maintenance Schedule", "maintenanceHeading")
        title.setWordWrap(False)
        heading.addWidget(title)
        heading.addStretch()
        ordering = _label("Ordered by due date", "maintenanceMuted")
        ordering.setWordWrap(False)
        heading.addWidget(ordering)
        listing.addLayout(heading)
        self.items_container = QWidget()
        self.items_layout = QVBoxLayout(self.items_container)
        self.items_layout.setContentsMargins(0, 0, 0, 0)
        self.items_layout.setSpacing(16)
        listing.addWidget(self.items_container)
        listing.addStretch()
        self.columns.addLayout(listing, 165)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_responsive()

    def _apply_responsive(self) -> None:
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

    def refresh(self) -> None:
        self._serial += 1
        serial = self._serial
        self._worker.submit(
            lambda: self.service.view(self.profile_id),
            lambda result: self._render(result) if serial == self._serial else None,
        )

    def _set_busy(self, busy: bool) -> None:
        self.add_button.setEnabled(not busy)
        self.items_container.setEnabled(not busy)

    def _show_error(self, error: Exception) -> None:
        self.status.setText(
            str(error) if isinstance(error, ValueError)
            else "The maintenance item could not be saved. Please try again."
        )
        self.status.setStyleSheet("color: #fb7185;")
        self.status.show()

    def _show_success(self, message: str) -> None:
        self.status.setText(message)
        self.status.setStyleSheet("color: #10b981;")
        self.status.show()
        self.refresh()

    @staticmethod
    def _date(field: QDateEdit) -> date:
        value = field.date()
        return date(value.year(), value.month(), value.day())

    def add_item(self) -> None:
        try:
            interval = int(self.interval_input.text().strip())
        except ValueError:
            self._show_error(ValueError("The repeat interval must be between 1 and 999."))
            return
        name = self.name_input.text()
        category = self.category_input.currentText()
        due = self._date(self.due_input)
        unit = self.unit_input.currentData()
        cost = self.cost_input.text()
        notes = self.notes_input.toPlainText()
        self._worker.submit(
            lambda: self.service.add(
                self.profile_id, name, category, due, interval, unit, cost, notes
            ),
            lambda _: self._after_add(name.strip()),
        )

    def _after_add(self, name: str) -> None:
        self.name_input.clear()
        self.interval_input.setText("1")
        self.cost_input.clear()
        self.notes_input.clear()
        self._show_success(f"Added {name}.")

    def _render(self, result: MaintenanceView) -> None:
        self.tracked_value.setText(str(result.total))
        self.overdue_value.setText(str(result.overdue))
        self.soon_value.setText(str(result.due_soon))
        _clear(self.items_layout)
        if not result.items:
            card, box = _card()
            box.addWidget(_label("Your Schedule Is Clear", "maintenanceHeading"))
            box.addWidget(_label(
                "Add something you want your future self to remember.", "maintenanceMuted"
            ))
            self.items_layout.addWidget(card)
        for item in result.items:
            self.items_layout.addWidget(self._item_card(item))
        if result.total > len(result.items):
            self.items_layout.addWidget(_label(
                f"Showing {len(result.items)} of {result.total} items.", "maintenanceMuted"
            ))

    def _item_card(self, item: MaintenanceEntry) -> QFrame:
        style = {"overdue": "maintenanceOverdue", "soon": "maintenanceSoon",
                 "upcoming": "maintenanceUpcoming"}[item.status]
        card, box = _card(style)
        main = QHBoxLayout()
        title = QVBoxLayout()
        title.addWidget(_label(item.name, "maintenanceText"))
        title.addWidget(_label(item.category.upper(), "maintenanceMuted"))
        main.addLayout(title, 1)
        due = QVBoxLayout()
        status_name = {"overdue": "Overdue", "soon": "Due Soon",
                       "upcoming": "Upcoming"}[item.status]
        due.addWidget(_label(status_name, "maintenanceMuted"))
        due.addWidget(_label(f"{item.next_due_date:%b %d, %Y}", "maintenanceText"))
        main.addLayout(due)
        box.addLayout(main)
        if item.notes:
            box.addWidget(_label(item.notes, "maintenanceMuted"))
        meta = [f"Every {item.recurrence_interval} {item.recurrence_unit}"]
        if item.estimated_cost is not None:
            meta.append(f"Est. ${item.estimated_cost:.2f}")
        if item.last_completed_date:
            meta.append(f"Last done {item.last_completed_date:%b %d}")
        box.addWidget(_label("  •  ".join(meta), "maintenanceMuted"))
        actions = QHBoxLayout()
        actions.addStretch()
        complete = QPushButton("Mark Complete")
        complete.setObjectName("maintenancePrimary")
        complete.setAccessibleName(f"Mark {item.name} complete")
        complete.clicked.connect(lambda: self._complete(item))
        actions.addWidget(complete)
        remove = QPushButton("×")
        remove.setObjectName("maintenanceDanger")
        remove.setAccessibleName(f"Remove {item.name}")
        remove.clicked.connect(lambda: self._confirm_delete(item))
        actions.addWidget(remove)
        box.addLayout(actions)
        return card

    def _complete(self, item: MaintenanceEntry) -> None:
        self._worker.submit(
            lambda: self.service.complete(self.profile_id, item.id),
            lambda due: self._show_success(
                f"Completed {item.name}. Next due {due:%b %d, %Y}."
            ),
        )

    def _confirm_delete(self, item: MaintenanceEntry) -> None:
        dialog = QDialog(self)
        dialog.setObjectName("maintenanceDeleteDialog")
        dialog.setWindowTitle("Remove maintenance item")
        dialog.setStyleSheet(
            STYLE + "QDialog#maintenanceDeleteDialog { background: #1a1533; }"
        )
        box = QVBoxLayout(dialog)
        box.setContentsMargins(24, 24, 24, 24)
        box.addWidget(_label("Remove this maintenance item?", "maintenanceHeading"))
        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton("Cancel")
        cancel.setObjectName("maintenanceSecondary")
        cancel.setDefault(True)
        cancel.clicked.connect(dialog.reject)
        buttons.addWidget(cancel)
        remove = QPushButton("Remove")
        remove.setObjectName("maintenanceDanger")
        remove.clicked.connect(dialog.accept)
        buttons.addWidget(remove)
        box.addLayout(buttons)
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        dialog.deleteLater()
        if accepted:
            self._worker.submit(
                lambda: self.service.delete(self.profile_id, item.id),
                lambda _: self._show_success(f"Removed {item.name}."),
            )

    def shutdown(self) -> None:
        self._worker.shutdown()
