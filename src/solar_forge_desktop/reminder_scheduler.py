"""Claim due reminders while a signed-in desktop window is open."""

from datetime import datetime, timezone
from typing import Callable

from PySide6.QtCore import QObject, QTimer, Signal

from solar_forge_desktop.medicine_reminders import DueMedicineReminder, MedicineReminderService
from solar_forge_desktop.reminders import CalendarReminderService, DueReminder
from solar_forge_desktop.workers import BackgroundWorker

DueItem = DueReminder | DueMedicineReminder


class ReminderScheduler(QObject):
    delivered = Signal(object)
    failed = Signal(str)

    def __init__(
        self, service: CalendarReminderService, profile_id: int, parent: QObject,
        clock: Callable[[], datetime] | None = None,
        medicine: MedicineReminderService | None = None,
    ):
        super().__init__(parent)
        self.service = service
        self.medicine = medicine
        self.profile_id = profile_id
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self._busy = False
        self._worker = BackgroundWorker(self, "solar-forge-calendar-reminders")
        self._worker.busy_changed.connect(self._set_busy)
        self._worker.failed.connect(self._failed)
        self._timer = QTimer(self)
        self._timer.setInterval(60 * 1000)
        self._timer.timeout.connect(self.check)

    def start(self) -> None:
        self._timer.start()
        QTimer.singleShot(0, self.check)

    def check(self) -> None:
        if self._busy:
            return

        def claim() -> tuple[DueItem, ...]:
            now = self.clock()
            result = []
            for service in (self.service, self.medicine):
                if service is None:
                    continue
                for reminder in service.due(self.profile_id, now):
                    if service.mark_delivered(self.profile_id, reminder, now):
                        result.append(reminder)
            return tuple(sorted(result, key=lambda reminder: reminder.due_at))

        self._worker.submit(claim, self._completed)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy

    def _failed(self, error: Exception) -> None:
        self.failed.emit(f"Reminders could not be checked: {error}")

    def _completed(self, reminders: tuple[DueItem, ...]) -> None:
        if reminders:
            self.delivered.emit(reminders)

    def shutdown(self) -> None:
        self._timer.stop()
        self._worker.shutdown()
