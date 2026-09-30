"""Shared styling for Qt-owned date and date/time calendar popups."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QTextCharFormat
from PySide6.QtWidgets import QCalendarWidget, QToolButton

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

