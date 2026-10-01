"""Native month and week calendar, matching the web event form and board."""

from datetime import date, datetime, time, timedelta

from PySide6.QtCore import QDate, Qt, QTime
from PySide6.QtWidgets import (
    QBoxLayout,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from solar_forge_desktop.calendar import CalendarService, CalendarView, Event, Occurrence, tag_color
from solar_forge_desktop.calendar_widgets import CALENDAR_STYLE, SELECTOR_STYLE, style_calendar
from solar_forge_desktop.workers import BackgroundWorker

STYLE = """
QWidget#calendarPage, QWidget#calendarBody, QWidget#calendarBoardBody {
    background: #0a0712; }
QScrollArea#calendarScroll, QScrollArea#calendarGridScroll { background: transparent;
    border: none; }
QFrame#calendarCard, QFrame#calendarToolbar, QFrame#calendarGridCard {
    background: #1a1533; border: 1px solid #302943; border-radius: 16px; }
QFrame#calendarCell { background: #1c172f; border: 1px solid #302943; }
QFrame#calendarOutside { background: #141023; border: 1px solid #302943; }
QFrame#calendarToday { background: #282047; border: 1px solid #674394; }
QFrame#calendarEvent { background: #251f3d; border: none; border-radius: 7px; }
QLabel#calendarEyebrow { color: #ec4899; font-size: 11px; font-weight: 700; }
QLabel#calendarTitle { color: #f3f4f6; font-size: 32px; font-weight: 700; }
QLabel#calendarHeading { color: #f3f4f6; font-size: 19px; font-weight: 700; }
QLabel#calendarText { color: #f3f4f6; font-size: 13px; }
QLabel#calendarMuted, QLabel#calendarWeekday { color: #a1a1aa; font-size: 12px; }
QLabel#calendarStatus { color: #fb7185; }
QLabel#calendarDayNumber { color: #f3f4f6; font-size: 14px; font-weight: 700; }
QLineEdit#calendarInput, QTextEdit#calendarInput, QDateEdit#calendarInput,
QTimeEdit#calendarInput, QComboBox#calendarInput { background: #211b30;
    color: #f3f4f6; border: 1px solid #39314e; border-radius: 9px;
    padding: 8px 10px; }
QComboBox#calendarInput QAbstractItemView { background: #211b30; color: #f3f4f6; }
QDateEdit::up-button, QDateEdit::down-button, QTimeEdit::up-button,
QTimeEdit::down-button { background: #302943; width: 18px; }
QPushButton#calendarPrimary { background: #8b5cf6; color: white; border: 0;
    border-radius: 9px; padding: 10px 14px; font-weight: 700; }
QPushButton#calendarSecondary { background: #292143; color: #f3f4f6;
    border: 1px solid #483a64; border-radius: 9px; padding: 8px 12px; }
QPushButton#calendarDanger { background: #3a1d39; color: #fb7185;
    border: 1px solid #5b3048; border-radius: 7px; padding: 3px 7px; }
QScrollBar:vertical, QScrollBar:horizontal { background: #151027; }
QScrollBar::handle:vertical, QScrollBar::handle:horizontal { background: #483a64;
    border-radius: 5px; min-width: 24px; min-height: 24px; }
""" + CALENDAR_STYLE + SELECTOR_STYLE


def _label(text: str, name: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName(name)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    return label


def _button(text: str, name: str, callback) -> QPushButton:
    button = QPushButton(text)
    button.setObjectName(name)
    button.clicked.connect(callback)
    return button


def _date_value(value: QDateEdit) -> date:
    day = value.date()
    return date(day.year(), day.month(), day.day())


def _set_date(value: QDateEdit, day: date) -> None:
    value.setDate(QDate(day.year, day.month, day.day))


def _clear(layout: QGridLayout) -> None:
    while layout.count():
        part = layout.takeAt(0)
        if widget := part.widget():
            widget.deleteLater()


class CalendarPage(QWidget):
    def __init__(self, service: CalendarService, profile_id: int):
        super().__init__()
        self.service = service
        self.profile_id = profile_id
        self.selected = date.today()
        self.mode = "month"
        self.edit_id: int | None = None
        self._serial = 0
        self.setObjectName("calendarPage")
        self.setStyleSheet(STYLE)
        self._build()
        self._worker = BackgroundWorker(self, "solar-forge-calendar")
        self._worker.busy_changed.connect(self._set_busy)
        self._worker.failed.connect(self._show_error)

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setObjectName("calendarScroll")
        self.scroll.setWidgetResizable(True)
        outer.addWidget(self.scroll)
        body = QWidget()
        body.setObjectName("calendarBody")
        self.scroll.setWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(48, 36, 48, 40)
        layout.setSpacing(18)
        header = QHBoxLayout()
        title = QVBoxLayout()
        title.setSpacing(5)
        title.addWidget(_label("YOUR TIME", "calendarEyebrow"))
        title.addWidget(_label("Calendar", "calendarTitle"))
        title.addWidget(_label(
            "Plan one-time or recurring events in a monthly or weekly view.", "calendarMuted"))
        header.addLayout(title, 1)
        self.month_button = _button("Month", "calendarPrimary", lambda: self.set_mode("month"))
        self.week_button = _button("Week", "calendarSecondary", lambda: self.set_mode("week"))
        header.addWidget(self.month_button, 0, Qt.AlignmentFlag.AlignBottom)
        header.addWidget(self.week_button, 0, Qt.AlignmentFlag.AlignBottom)
        layout.addLayout(header)
        self.status = _label("", "calendarStatus")
        self.status.setAccessibleName("Calendar status")
        layout.addWidget(self.status)
        self.status.hide()
        self.columns = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.columns.setSpacing(24)
        self._build_form()
        self._build_board()
        layout.addLayout(self.columns, 1)
        layout.addStretch()
        self._apply_responsive()

    def _input(self, accessible: str, placeholder: str = "") -> QLineEdit:
        field = QLineEdit()
        field.setObjectName("calendarInput")
        field.setAccessibleName(accessible)
        field.setPlaceholderText(placeholder)
        return field

    def _date_input(self, accessible: str) -> QDateEdit:
        field = QDateEdit()
        field.setObjectName("calendarInput")
        field.setAccessibleName(accessible)
        field.setDisplayFormat("MMM d, yyyy")
        field.setCalendarPopup(True)
        style_calendar(field.calendarWidget())
        _set_date(field, self.selected)
        return field

    def _time_input(self, accessible: str, hour: int) -> QTimeEdit:
        field = QTimeEdit()
        field.setObjectName("calendarInput")
        field.setAccessibleName(accessible)
        field.setDisplayFormat("h:mm AP")
        field.setTime(QTime(hour, 0))
        return field

    def _form_field(self, box: QVBoxLayout, label: str, widget: QWidget) -> None:
        box.addWidget(_label(label, "calendarMuted"))
        box.addWidget(widget)

    def _build_form(self) -> None:
        self.form_card = QFrame()
        self.form_card.setObjectName("calendarCard")
        self.form_card.setMinimumWidth(270)
        form = QVBoxLayout(self.form_card)
        form.setContentsMargins(22, 20, 22, 20)
        form.setSpacing(10)
        self.form_eyebrow = _label("NEW EVENT", "calendarEyebrow")
        self.form_heading = _label("Add to Calendar", "calendarHeading")
        self.form_hint = _label("Reuse an existing tag or type a new one.", "calendarMuted")
        for widget in (self.form_eyebrow, self.form_heading, self.form_hint):
            form.addWidget(widget)
        self.title_input = self._input("Event title", "Dentist appointment")
        self.title_input.setMaxLength(150)
        self._form_field(form, "Title", self.title_input)
        self.description_input = QTextEdit()
        self.description_input.setObjectName("calendarInput")
        self.description_input.setAccessibleName("Event description")
        self.description_input.setPlaceholderText("Anything useful to remember")
        self.description_input.setFixedHeight(72)
        self._form_field(form, "Description · Optional", self.description_input)
        self.category_input = self._input("Event tag", "Personal")
        self.category_input.setMaxLength(50)
        self._form_field(form, "Tag", self.category_input)
        self.visibility_input = QComboBox()
        self.visibility_input.setObjectName("calendarInput")
        self.visibility_input.setAccessibleName("Event visibility")
        self.visibility_input.addItem("Only me", "private")
        self.visibility_input.addItem("Household", "household")
        self._form_field(form, "Visible to", self.visibility_input)
        self.all_day_input = QCheckBox("All-day event")
        self.all_day_input.toggled.connect(self._update_fields)
        form.addWidget(self.all_day_input)
        self.start_date_input = self._date_input("Start date")
        self._form_field(form, "Start Date", self.start_date_input)
        self.start_time_input = self._time_input("Start time", 9)
        self._form_field(form, "Start Time", self.start_time_input)
        self.end_date_enabled = QCheckBox("Set end date")
        self.end_date_enabled.toggled.connect(self._update_fields)
        form.addWidget(self.end_date_enabled)
        self.end_date_input = self._date_input("End date")
        form.addWidget(self.end_date_input)
        self.end_time_enabled = QCheckBox("Set end time")
        self.end_time_enabled.toggled.connect(self._update_fields)
        form.addWidget(self.end_time_enabled)
        self.end_time_input = self._time_input("End time", 10)
        form.addWidget(self.end_time_input)
        self.recurrence_input = QComboBox()
        self.recurrence_input.setObjectName("calendarInput")
        self.recurrence_input.setAccessibleName("Repeats")
        for label, value in (("Does not repeat", "none"), ("Daily", "daily"),
                             ("Weekly", "weekly"), ("Monthly", "monthly"),
                             ("Yearly", "yearly")):
            self.recurrence_input.addItem(label, value)
        self.recurrence_input.currentIndexChanged.connect(self._update_fields)
        self._form_field(form, "Repeats", self.recurrence_input)
        self.until_enabled = QCheckBox("Repeat until")
        self.until_enabled.toggled.connect(self._update_fields)
        form.addWidget(self.until_enabled)
        self.until_input = self._date_input("Repeat until")
        form.addWidget(self.until_input)
        actions = QHBoxLayout()
        self.cancel_button = _button("Cancel", "calendarSecondary", self.clear_form)
        self.cancel_button.hide()
        actions.addWidget(self.cancel_button)
        self.save_button = _button("Add Event", "calendarPrimary", self.save_event)
        actions.addWidget(self.save_button, 1)
        form.addLayout(actions)
        self.columns.addWidget(self.form_card, 72, Qt.AlignmentFlag.AlignTop)
        self._update_fields()

    def _build_board(self) -> None:
        board = QVBoxLayout()
        board.setSpacing(14)
        toolbar = QFrame()
        toolbar.setObjectName("calendarToolbar")
        toolbar_row = QHBoxLayout(toolbar)
        toolbar_row.setContentsMargins(14, 12, 14, 12)
        toolbar_row.addWidget(_button("←", "calendarSecondary", lambda: self.navigate(-1)))
        heading = QVBoxLayout()
        self.period_label = _label("", "calendarHeading")
        self.count_label = _label("", "calendarMuted")
        heading.addWidget(self.period_label)
        heading.addWidget(self.count_label)
        toolbar_row.addLayout(heading, 1)
        toolbar_row.addWidget(_button("Today", "calendarSecondary", self.today))
        toolbar_row.addWidget(_button("→", "calendarSecondary", lambda: self.navigate(1)))
        board.addWidget(toolbar)
        card = QFrame()
        card.setObjectName("calendarGridCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        self.grid_scroll = QScrollArea()
        self.grid_scroll.setObjectName("calendarGridScroll")
        self.grid_scroll.setWidgetResizable(True)
        self.grid_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        grid_body = QWidget()
        grid_body.setObjectName("calendarBoardBody")
        grid_body.setMinimumWidth(760)
        self.grid_scroll.setWidget(grid_body)
        self.grid_layout = QGridLayout(grid_body)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setHorizontalSpacing(0)
        self.grid_layout.setVerticalSpacing(0)
        card_layout.addWidget(self.grid_scroll)
        board.addWidget(card, 1)
        self.columns.addLayout(board, 200)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "columns"):
            self._apply_responsive()

    def _apply_responsive(self) -> None:
        self.columns.setDirection(QBoxLayout.Direction.TopToBottom if self.width() < 1030
                                  else QBoxLayout.Direction.LeftToRight)

    def _update_fields(self, *_args) -> None:
        all_day = self.all_day_input.isChecked()
        self.start_time_input.setVisible(not all_day)
        self.end_time_enabled.setVisible(not all_day)
        self.end_time_input.setVisible(not all_day and self.end_time_enabled.isChecked())
        self.end_date_input.setVisible(self.end_date_enabled.isChecked())
        repeating = self.recurrence_input.currentData() != "none"
        self.until_enabled.setVisible(repeating)
        self.until_input.setVisible(repeating and self.until_enabled.isChecked())

    def activate(self) -> None:
        self.refresh()

    def refresh(self) -> None:
        self._serial += 1
        serial = self._serial
        selected, mode = self.selected, self.mode
        self._worker.submit(
            lambda: self.service.view(self.profile_id, selected, mode),
            lambda result: self._render(result) if serial == self._serial else None,
        )

    def _set_busy(self, busy: bool) -> None:
        self.save_button.setEnabled(not busy)
        self.grid_scroll.setEnabled(not busy)

    def _show_error(self, error: Exception) -> None:
        self.status.setText(str(error) if isinstance(error, ValueError)
                            else "The calendar could not be updated. Please try again.")
        self.status.setStyleSheet("color: #fb7185;")
        self.status.show()

    def _success(self, message: str) -> None:
        self.status.setText(message)
        self.status.setStyleSheet("color: #10b981;")
        self.status.show()
        self.refresh()

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self.month_button.setObjectName("calendarPrimary" if mode == "month"
                                        else "calendarSecondary")
        self.week_button.setObjectName("calendarPrimary" if mode == "week"
                                       else "calendarSecondary")
        for button in (self.month_button, self.week_button):
            button.style().unpolish(button)
            button.style().polish(button)
        self.refresh()

    def navigate(self, direction: int) -> None:
        view = self.service.view(self.profile_id, self.selected, self.mode)
        self.selected = view.previous if direction < 0 else view.next
        self.refresh()

    def today(self) -> None:
        self.selected = date.today()
        self.refresh()

    def _render(self, view: CalendarView) -> None:
        self.period_label.setText(view.label)
        self.count_label.setText(f"{view.event_count} event{'s' if view.event_count != 1 else ''}")
        if view.categories and not self.category_input.text():
            self.category_input.setPlaceholderText(", ".join(view.categories[:3]))
        _clear(self.grid_layout)
        self.grid_scroll.setFixedHeight(
            446 if view.mode == "week" else 38 + (len(view.days) // 7) * 140
        )
        if view.mode == "month":
            for column, weekday in enumerate(("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")):
                header = _label(weekday, "calendarWeekday")
                header.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.grid_layout.addWidget(header, 0, column)
        for index, (day, items) in enumerate(view.days):
            cell = QFrame()
            cell.setObjectName("calendarToday" if day == date.today() else
                               "calendarOutside" if view.mode == "month"
                               and day.month != view.selected.month else "calendarCell")
            cell.setMinimumHeight(140 if view.mode == "month" else 420)
            box = QVBoxLayout(cell)
            box.setContentsMargins(7, 7, 7, 7)
            box.setSpacing(5)
            day_label = _label(str(day.day) if view.mode == "month" else
                               f"{day:%a}  {day.day}", "calendarDayNumber")
            day_label.setAlignment(Qt.AlignmentFlag.AlignRight)
            box.addWidget(day_label)
            for item in items:
                box.addWidget(self._event_card(item, view.mode))
            if view.mode == "week" and not items:
                box.addWidget(_label("No events", "calendarMuted"))
            box.addStretch()
            row = index // 7 + (1 if view.mode == "month" else 0)
            self.grid_layout.addWidget(cell, row, index % 7)
        for column in range(7):
            self.grid_layout.setColumnStretch(column, 1)

    def _event_card(self, item: Occurrence, mode: str) -> QFrame:
        event = item.event
        card = QFrame()
        card.setObjectName("calendarEvent")
        card.setStyleSheet(
            f"QFrame#calendarEvent {{ border-left: 3px solid {tag_color(event.category)}; }}"
        )
        box = QVBoxLayout(card)
        box.setContentsMargins(6, 5, 6, 5)
        box.setSpacing(2)
        if event.all_day:
            timing = "All day"
        elif item.ends_at.date() == item.starts_at.date():
            timing = f"{item.starts_at:%I:%M %p} - {item.ends_at:%I:%M %p}"
        elif mode == "week":
            timing = f"{item.starts_at:%b %d, %I:%M %p} - {item.ends_at:%b %d, %I:%M %p}"
        else:
            timing = item.starts_at.strftime("%I:%M %p")
        box.addWidget(_label(timing, "calendarMuted"))
        box.addWidget(_label(event.title, "calendarText"))
        tag = event.category + (f" · {event.recurrence.title()}"
                                if event.recurrence != "none" else "")
        category = _label(tag, "calendarMuted")
        category.setStyleSheet(f"color: {tag_color(event.category)};")
        box.addWidget(category)
        box.addWidget(_label(
            "Household" if event.visibility == "household" else "Only me",
            "calendarMuted",
        ))
        if mode == "week" and event.description:
            box.addWidget(_label(event.description, "calendarMuted"))
        actions = QHBoxLayout()
        edit = _button("✎", "calendarSecondary", lambda: self.edit_event(event.id))
        edit.setAccessibleName(f"Edit {event.title}")
        actions.addWidget(edit)
        if event.profile_id == self.profile_id:
            remove = _button("×", "calendarDanger", lambda: self.delete_event(event))
            remove.setAccessibleName(f"Remove {event.title}")
            actions.addWidget(remove)
        actions.addStretch()
        box.addLayout(actions)
        return card

    def clear_form(self) -> None:
        self.edit_id = None
        self.form_eyebrow.setText("NEW EVENT")
        self.form_heading.setText("Add to Calendar")
        self.form_hint.setText("Reuse an existing tag or type a new one.")
        self.save_button.setText("Add Event")
        self.cancel_button.hide()
        self.title_input.clear()
        self.description_input.clear()
        self.category_input.clear()
        self.visibility_input.setCurrentIndex(0)
        self.visibility_input.setEnabled(True)
        self.all_day_input.setChecked(False)
        self.end_date_enabled.setChecked(False)
        self.end_time_enabled.setChecked(False)
        self.recurrence_input.setCurrentIndex(0)
        self.until_enabled.setChecked(False)
        _set_date(self.start_date_input, self.selected)
        self.start_time_input.setTime(QTime(9, 0))
        self.end_time_input.setTime(QTime(10, 0))
        self._update_fields()

    def edit_event(self, event_id: int) -> None:
        try:
            event = self.service.get(self.profile_id, event_id)
        except ValueError as error:
            self._show_error(error)
            return
        self.edit_id = event.id
        self.form_eyebrow.setText("EDIT EVENT")
        self.form_heading.setText("Update Event")
        self.form_hint.setText(
            "Changes apply to the full recurring series." if event.recurrence != "none"
            else "Reuse an existing tag or type a new one."
        )
        self.save_button.setText("Save Changes")
        self.cancel_button.show()
        self.title_input.setText(event.title)
        self.description_input.setPlainText(event.description or "")
        self.category_input.setText(event.category)
        self.visibility_input.setCurrentIndex(self.visibility_input.findData(event.visibility))
        self.visibility_input.setEnabled(event.profile_id == self.profile_id)
        self.all_day_input.setChecked(event.all_day)
        _set_date(self.start_date_input, event.starts_at.date())
        self.start_time_input.setTime(QTime(event.starts_at.hour, event.starts_at.minute))
        end_day = (event.ends_at.date() - timedelta(days=1) if event.all_day
                   else event.ends_at.date())
        self.end_date_enabled.setChecked(end_day != event.starts_at.date())
        _set_date(self.end_date_input, end_day)
        self.end_time_enabled.setChecked(not event.all_day)
        self.end_time_input.setTime(QTime(event.ends_at.hour, event.ends_at.minute))
        self.recurrence_input.setCurrentIndex(self.recurrence_input.findData(event.recurrence))
        self.until_enabled.setChecked(event.recurrence_until is not None)
        if event.recurrence_until:
            _set_date(self.until_input, event.recurrence_until)
        self._update_fields()
        self.scroll.ensureWidgetVisible(self.form_card)

    def save_event(self) -> None:
        start_day = _date_value(self.start_date_input)
        end_day = (_date_value(self.end_date_input) if self.end_date_enabled.isChecked()
                   else start_day)
        all_day = self.all_day_input.isChecked()
        start_clock = time.min if all_day else time(self.start_time_input.time().hour(),
                                                    self.start_time_input.time().minute())
        start = datetime.combine(start_day, start_clock)
        if all_day:
            end = datetime.combine(end_day + timedelta(days=1), time.min)
        elif self.end_time_enabled.isChecked():
            end = datetime.combine(end_day, time(self.end_time_input.time().hour(),
                                                  self.end_time_input.time().minute()))
        else:
            end = start + timedelta(hours=1)
        recurrence = self.recurrence_input.currentData()
        until = _date_value(self.until_input) if recurrence != "none" and \
            self.until_enabled.isChecked() else None
        title, description, category = (self.title_input.text(),
                                         self.description_input.toPlainText(),
                                         self.category_input.text())
        event_id = self.edit_id
        visibility = (self.visibility_input.currentData()
                      if self.visibility_input.isEnabled() else None)
        self._worker.submit(
            lambda: self.service.save(self.profile_id, title, description, category,
                                      start, end, all_day, recurrence, until, event_id,
                                      visibility),
            lambda _: self._after_save(title.strip(), start_day, event_id),
        )

    def _after_save(self, title: str, start_day: date, event_id: int | None) -> None:
        self.selected = start_day
        self.clear_form()
        self._success(f"{'Updated' if event_id else 'Added'} {title}.")

    def delete_event(self, event: Event) -> None:
        suffix = " and its full series" if event.recurrence != "none" else ""
        answer = QMessageBox.question(self, "Remove Event", f"Remove {event.title}{suffix}?",
                                      QMessageBox.StandardButton.Yes |
                                      QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._worker.submit(
            lambda: self.service.delete(self.profile_id, event.id),
            lambda _: self._after_delete(event),
        )

    def _after_delete(self, event: Event) -> None:
        if self.edit_id == event.id:
            self.clear_form()
        self._success(f"Removed {event.title}.")

    def shutdown(self) -> None:
        self._worker.shutdown()
