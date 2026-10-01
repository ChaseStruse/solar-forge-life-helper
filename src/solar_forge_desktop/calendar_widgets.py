"""Shared styling for selector controls and Qt-owned calendar popups."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QTextCharFormat
from PySide6.QtWidgets import QCalendarWidget, QToolButton

_CHEVRON = (Path(__file__).parent / "assets" / "selector-chevron.svg").as_posix()

SELECTOR_STYLE = f"""
QComboBox::drop-down, QDateEdit::drop-down, QDateTimeEdit::drop-down {{
    subcontrol-origin: padding; subcontrol-position: top right;
    width: 28px; border-left: 1px solid #483a64;
    border-top-right-radius: 8px; border-bottom-right-radius: 8px;
    background: #302943; }}
QComboBox::drop-down:hover, QDateEdit::drop-down:hover,
QDateTimeEdit::drop-down:hover {{ background: #483a64; }}
QComboBox::down-arrow, QDateEdit::down-arrow, QDateTimeEdit::down-arrow {{
    image: url("{_CHEVRON}"); width: 12px; height: 12px; }}
QComboBox QAbstractItemView {{ background: #211b30; color: #f3f4f6;
    border: 1px solid #483a64; outline: none;
    selection-background-color: #483a64; selection-color: #ffffff; }}
QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {{
    background: #302943; border-left: 1px solid #483a64; width: 24px; }}
QAbstractSpinBox::up-button:hover, QAbstractSpinBox::down-button:hover {{
    background: #483a64; }}
QAbstractSpinBox::up-arrow, QAbstractSpinBox::down-arrow {{
    width: 8px; height: 8px; }}
"""

CALENDAR_STYLE = """
QCalendarWidget#solarForgeCalendar { background: #151027; color: #f3f4f6;
    border: 1px solid #483a64; }
QCalendarWidget#solarForgeCalendar QWidget#qt_calendar_navigationbar {
    background: #211b30; }
QCalendarWidget#solarForgeCalendar QToolButton { color: #f3f4f6;
    background: #211b30; border: none; border-radius: 6px; padding: 6px; }
QCalendarWidget#solarForgeCalendar QToolButton:hover { background: #483a64; }
QCalendarWidget#solarForgeCalendar QMenu, QCalendarWidget#solarForgeCalendar QSpinBox {
    background: #211b30; color: #f3f4f6; border: 1px solid #483a64; }
QCalendarWidget#solarForgeCalendar QAbstractItemView {
    background: #151027; color: #f3f4f6; selection-background-color: #8b5cf6;
    selection-color: #ffffff; outline: none; }
"""


def style_calendar(calendar: QCalendarWidget) -> None:
    """Apply the shared Solar Forge palette to Qt's own calendar popup."""
    calendar.setObjectName("solarForgeCalendar")
    calendar.setMinimumSize(300, 255)
    calendar.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
    header = QTextCharFormat()
    header.setForeground(QColor("#a1a1aa"))
    header.setBackground(QColor("#211b30"))
    calendar.setHeaderTextFormat(header)
    weekend = QTextCharFormat()
    weekend.setForeground(QColor("#f3f4f6"))
    for day in (Qt.DayOfWeek.Saturday, Qt.DayOfWeek.Sunday):
        calendar.setWeekdayTextFormat(day, weekend)
    for name, label in (("qt_calendar_prevmonth", "‹"),
                        ("qt_calendar_nextmonth", "›")):
        button = calendar.findChild(QToolButton, name)
        button.setIcon(QIcon())
        button.setText(label)
