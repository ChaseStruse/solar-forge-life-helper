"""Native Medicine Tracker page."""

from datetime import datetime
from typing import Callable

from PySide6.QtCore import QDateTime, Qt
from PySide6.QtWidgets import (
    QBoxLayout,
    QDateTimeEdit,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from solar_forge_desktop.calendar_widgets import CALENDAR_STYLE, SELECTOR_STYLE, style_calendar
from solar_forge_desktop.medicine import MedicineService, MedicineView
from solar_forge_desktop.storage import MedicineItem
from solar_forge_desktop.workers import BackgroundWorker

STYLE = """
QWidget#medicinePage, QWidget#medicineBody, QWidget#medicineList { background: #0a0712; }
QScrollArea#medicineScroll { background: #0a0712; border: none; }
QFrame#medicineCard { background: #1a1533; border: 1px solid #302943; border-radius: 16px; }
QLabel#medicineTitle { color: #f3f4f6; font-size: 32px; font-weight: 700; }
QLabel#medicineHeading { color: #f3f4f6; font-size: 18px; font-weight: 700; }
QLabel#medicineValue { color: #f3f4f6; font-size: 23px; font-weight: 700; }
QLabel#medicineText { color: #f3f4f6; font-size: 14px; }
QLabel#medicineMuted { color: #a1a1aa; }
QLabel#medicineStatus { color: #fb7185; }
QLineEdit#medicineInput, QDateTimeEdit#medicineInput { background: #211b30;
    color: #f3f4f6; border: 1px solid #302943; border-radius: 9px; padding: 10px 12px; }
QLineEdit#medicineInput:focus, QDateTimeEdit#medicineInput:focus { border-color: #8b5cf6; }
QPushButton#medicinePrimary { color: white; border: none; border-radius: 10px;
    background: #8b5cf6; padding: 10px 14px; font-weight: 700; }
QPushButton#medicineDanger { background: #3a1d39; color: #fb7185;
    border: 1px solid #5b3048; border-radius: 9px; padding: 8px 12px; }
""" + CALENDAR_STYLE + SELECTOR_STYLE


def _label(text: str, name: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName(name)
    label.setWordWrap(True)
    label.setTextFormat(Qt.TextFormat.PlainText)
    return label


def _card() -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("medicineCard")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(22, 20, 22, 20)
    layout.setSpacing(10)
    return frame, layout


class MedicinePage(QWidget):
    def __init__(self, service: MedicineService, profile_id: int):
        super().__init__()
        self.service = service
        self.profile_id = profile_id
        self._serial = 0
        self.setObjectName("medicinePage")
        self.setStyleSheet(STYLE)
        self._build()
        self._worker = BackgroundWorker(self, "solar-forge-medicine")
        self._worker.busy_changed.connect(self._set_busy)
        self._worker.failed.connect(self._show_error)

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setObjectName("medicineScroll")
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        body = QWidget()
        body.setObjectName("medicineBody")
        scroll.setWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(48, 36, 48, 40)
        layout.setSpacing(16)
        layout.addWidget(_label("Medicine Tracker", "medicineTitle"))
        layout.addWidget(_label(
            "Record medicine given to people and pets, and keep the next dose in view.",
            "medicineMuted",
        ))
        self.status = _label("", "medicineStatus")
        self.status.setAccessibleName("Medicine status")
        layout.addWidget(self.status)

        summary = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.summary = summary
        summary.setSpacing(16)
        self.total_value = self._summary(summary, "DOSE RECORDS")
        self.next_value = self._summary(summary, "NEXT DOSE")
        self.people_value = self._summary(summary, "FOR PEOPLE & PETS")
        layout.addLayout(summary)

        self.columns = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.columns.setSpacing(24)
        layout.addLayout(self.columns)
        layout.addStretch()

        form, fields = _card()
        fields.addWidget(_label("Log a Dose", "medicineHeading"))
        self.recipient_input = self._line(fields, "WHO IS IT FOR?", "Recipient", 100)
        self.name_input = self._line(fields, "MEDICINE", "Medicine name", 150)
        self.dosage_input = self._line(fields, "DOSAGE", "Dosage", 100)
        now = QDateTime.currentDateTime()
        self.given_input = self._date(fields, "GIVEN AT", "Given at", now)
        self.next_input = self._date(fields, "NEXT DOSE AT", "Next dose at", now.addDays(1))
        self.save_button = QPushButton("Save Dose")
        self.save_button.setObjectName("medicinePrimary")
        self.save_button.setAccessibleName("Save medicine dose")
        self.save_button.clicked.connect(self.add_log)
        fields.addWidget(self.save_button)
        self.columns.addWidget(form, 2, Qt.AlignmentFlag.AlignTop)

        listing = QVBoxLayout()
        self.list_heading = _label("Scheduled Doses (0)", "medicineHeading")
        listing.addWidget(self.list_heading)
        self.list_widget = QWidget()
        self.list_widget.setObjectName("medicineList")
        self.list_layout = QVBoxLayout(self.list_widget)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(12)
        listing.addWidget(self.list_widget)
        listing.addStretch()
        self.columns.addLayout(listing, 3)
        self._apply_responsive()

    def _summary(self, row: QBoxLayout, title: str) -> QLabel:
        frame, box = _card()
        box.addWidget(_label(title, "medicineMuted"))
        value = _label("—", "medicineValue")
        value.setAccessibleName(title.title())
        box.addWidget(value)
        row.addWidget(frame, 1)
        return value

    def _line(self, form: QVBoxLayout, title: str, accessible: str, max_length: int) -> QLineEdit:
        form.addWidget(_label(title, "medicineMuted"))
        field = QLineEdit()
        field.setObjectName("medicineInput")
        field.setAccessibleName(accessible)
        field.setMaxLength(max_length)
        form.addWidget(field)
        return field

    def _date(
        self, form: QVBoxLayout, title: str, accessible: str, value: QDateTime
    ) -> QDateTimeEdit:
        form.addWidget(_label(title, "medicineMuted"))
        field = QDateTimeEdit()
        field.setObjectName("medicineInput")
        field.setAccessibleName(accessible)
        field.setDisplayFormat("MMM d, yyyy  h:mm AP")
        field.setDateTime(value)
        field.setCalendarPopup(True)
        style_calendar(field.calendarWidget())
        form.addWidget(field)
        return field

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

    def _run(self, action: Callable[[], object], done: Callable[[object], None]) -> None:
        self._worker.submit(action, done)

    def _set_busy(self, busy: bool) -> None:
        self.save_button.setEnabled(not busy)

    def _show_error(self, error: Exception) -> None:
        self.status.setText(
            str(error) if isinstance(error, ValueError) else
            "The medicine log could not be saved. Please try again."
        )
        self.status.setStyleSheet("color: #fb7185;")

    def refresh(self) -> None:
        self._serial += 1
        serial = self._serial
        self._run(
            lambda: self.service.view(self.profile_id),
            lambda result: self._render(result) if serial == self._serial else None,
        )

    def _render(self, result: MedicineView) -> None:
        self.total_value.setText(str(result.total_count))
        self.people_value.setText(str(result.recipient_count))
        self.next_value.setText(
            self._display_time(result.logs[0].next_due_at) if result.logs else "No dose scheduled"
        )
        self.list_heading.setText(f"Scheduled Doses ({result.total_count})")
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().hide()
                item.widget().deleteLater()
        if not result.logs:
            empty, box = _card()
            box.addWidget(_label("No doses recorded yet.", "medicineHeading"))
            box.addWidget(_label("Log a dose to start your schedule.", "medicineMuted"))
            self.list_layout.addWidget(empty)
            return
        for item in result.logs:
            self.list_layout.addWidget(self._log_card(item))
        if result.total_count > len(result.logs):
            self.list_layout.addWidget(_label(
                f"Showing the next {len(result.logs)} of {result.total_count} doses.",
                "medicineMuted",
            ))

    @staticmethod
    def _display_time(value: str) -> str:
        return datetime.fromisoformat(value).strftime("%b %d, %Y  %I:%M %p")

    def _log_card(self, item: MedicineItem) -> QFrame:
        card, box = _card()
        card.setAccessibleName(f"Dose for {item.recipient}: {item.medicine_name}")
        header = QHBoxLayout()
        header.addWidget(_label(item.medicine_name, "medicineHeading"), 1)
        delete = QPushButton("Delete")
        delete.setObjectName("medicineDanger")
        delete.setAccessibleName(f"Delete {item.medicine_name} for {item.recipient}")
        delete.clicked.connect(lambda _checked=False, entry=item: self._confirm_delete(entry))
        header.addWidget(delete)
        box.addLayout(header)
        box.addWidget(_label(f"For {item.recipient} · {item.dosage}", "medicineText"))
        box.addWidget(_label(f"Given: {self._display_time(item.given_at)}", "medicineMuted"))
        box.addWidget(_label(f"Next dose: {self._display_time(item.next_due_at)}", "medicineMuted"))
        return card

    def add_log(self) -> None:
        recipient = self.recipient_input.text()
        name = self.name_input.text()
        dosage = self.dosage_input.text()
        given = self.given_input.dateTime().toString("yyyy-MM-ddTHH:mm")
        due = self.next_input.dateTime().toString("yyyy-MM-ddTHH:mm")
        self._run(
            lambda: self.service.add_log(self.profile_id, recipient, name, dosage, given, due),
            lambda _: self._after_add(),
        )

    def _after_add(self) -> None:
        self.recipient_input.clear()
        self.name_input.clear()
        self.dosage_input.clear()
        now = QDateTime.currentDateTime()
        self.given_input.setDateTime(now)
        self.next_input.setDateTime(now.addDays(1))
        self.status.setText("Medicine dose saved.")
        self.status.setStyleSheet("color: #10b981;")
        self.refresh()

    def _confirm_delete(self, item: MedicineItem) -> None:
        dialog = QDialog(self)
        dialog.setObjectName("medicineDeleteDialog")
        dialog.setWindowTitle("Delete medicine dose")
        dialog.setStyleSheet("""
            QDialog#medicineDeleteDialog { background: #1a1533; color: #f3f4f6; }
            QLabel { color: #f3f4f6; }
            QPushButton { background: #292143; color: #f3f4f6; padding: 10px 16px;
                border: 1px solid #483a64; border-radius: 9px; }
            QPushButton#medicineConfirmDelete { background: #be3153; border-color: #e44970; }
        """)
        box = QVBoxLayout(dialog)
        box.setContentsMargins(24, 24, 24, 24)
        box.addWidget(_label(
            f"Delete {item.medicine_name} for {item.recipient}?", "medicineHeading"
        ))
        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton("Cancel")
        cancel.setDefault(True)
        cancel.clicked.connect(dialog.reject)
        buttons.addWidget(cancel)
        confirm = QPushButton("Delete dose")
        confirm.setObjectName("medicineConfirmDelete")
        confirm.clicked.connect(dialog.accept)
        buttons.addWidget(confirm)
        box.addLayout(buttons)
        cancel.setFocus()
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        dialog.deleteLater()
        if accepted:
            self._run(
                lambda: self.service.delete_log(self.profile_id, item.id),
                lambda _: self._after_delete(),
            )

    def _after_delete(self) -> None:
        self.status.setText("Medicine dose deleted.")
        self.status.setStyleSheet("color: #10b981;")
        self.refresh()

    def shutdown(self) -> None:
        self._worker.shutdown()
