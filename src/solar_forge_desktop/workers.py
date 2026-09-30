"""Serial background work with explicit GUI-thread delivery and shutdown."""

from concurrent.futures import Future, ThreadPoolExecutor
from typing import Callable

from PySide6.QtCore import QObject, Qt, Signal, Slot


class BackgroundWorker(QObject):
    """Each view owns one worker and shuts it down before closing its storage."""

    busy_changed = Signal(bool)
    failed = Signal(object)
    _finished = Signal(int, object)

    def __init__(self, parent: QObject, name: str):
        super().__init__(parent)
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix=name)
        self._pending: dict[int, Callable[[object], None]] = {}
        self._next_id = 0
        self._closing = False
        self._finished.connect(self._deliver, Qt.ConnectionType.QueuedConnection)

    def submit(self, action: Callable[[], object], done: Callable[[object], None]) -> None:
        if self._closing:
            return
        self._next_id += 1
        request_id = self._next_id
        was_idle = not self._pending
        self._pending[request_id] = done
        if was_idle:
            self.busy_changed.emit(True)
        future = self._executor.submit(action)
        future.add_done_callback(lambda result: self._finished.emit(request_id, result))

    @Slot(int, object)
    def _deliver(self, request_id: int, future: Future) -> None:
        if self._closing:
            return
        done = self._pending.pop(request_id)
        try:
            try:
                result = future.result()
            except Exception as exc:
                self.failed.emit(exc)
            else:
                done(result)
        finally:
            # A completion callback may queue a refresh; keep the view busy until
            # that refresh and every other outstanding operation have completed.
            if not self._pending:
                self.busy_changed.emit(False)

    def shutdown(self) -> None:
        """Finish the active operation, cancel queued work, and discard callbacks."""
        if self._closing:
            return
        self._closing = True
        self._pending.clear()
        self._executor.shutdown(wait=True, cancel_futures=True)
