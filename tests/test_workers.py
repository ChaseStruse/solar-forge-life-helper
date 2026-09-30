"""Background work must preserve GUI affinity, busy state, and shutdown safety."""

from threading import Event, Timer, get_ident

import pytest
from PySide6.QtCore import QObject

from solar_forge_desktop.workers import BackgroundWorker


def test_serial_work_delivers_on_gui_thread_and_stays_busy(qtbot, qapp) -> None:
    parent = QObject()
    worker = BackgroundWorker(parent, "test-worker")
    busy = []
    results = []
    first_started, release_first = Event(), Event()
    second_started, release_second = Event(), Event()
    gui_thread = get_ident()
    worker.busy_changed.connect(busy.append)

    def first():
        first_started.set()
        assert release_first.wait(5)
        return get_ident()

    def second():
        second_started.set()
        assert release_second.wait(5)
        return get_ident()

    def delivered(result):
        assert get_ident() == gui_thread
        assert result != gui_thread
        results.append(result)

    try:
        worker.submit(first, delivered)
        worker.submit(second, delivered)
        qtbot.waitUntil(first_started.is_set)
        assert not second_started.is_set()
        assert busy == [True]
        release_first.set()
        qtbot.waitUntil(lambda: len(results) == 1 and second_started.is_set())
        assert busy == [True]
        release_second.set()
        qtbot.waitUntil(lambda: len(results) == 2 and busy[-1] is False)
        assert busy == [True, False]
    finally:
        release_first.set()
        release_second.set()
        worker.shutdown()


@pytest.mark.parametrize("error", [ValueError("Invalid input"), OSError("Unavailable")])
def test_failure_is_delivered_and_next_operation_recovers(qtbot, error) -> None:
    parent = QObject()
    worker = BackgroundWorker(parent, "test-error")
    failures, results, busy = [], [], []
    worker.failed.connect(failures.append)
    worker.busy_changed.connect(busy.append)

    def fail():
        raise error

    try:
        worker.submit(fail, results.append)
        qtbot.waitUntil(lambda: failures == [error] and busy[-1] is False)
        assert results == []
        worker.submit(lambda: "recovered", results.append)
        qtbot.waitUntil(lambda: results == ["recovered"] and busy[-1] is False)
    finally:
        worker.shutdown()


def test_chained_refresh_keeps_busy_until_finished(qtbot) -> None:
    parent = QObject()
    worker = BackgroundWorker(parent, "test-refresh")
    busy, results = [], []
    worker.busy_changed.connect(busy.append)

    def refresh(_result):
        assert False not in busy
        worker.submit(lambda: "refreshed", results.append)

    try:
        worker.submit(lambda: "saved", refresh)
        qtbot.waitUntil(lambda: results == ["refreshed"] and busy[-1] is False)
        assert False not in busy[:-1]
    finally:
        worker.shutdown()


def test_shutdown_finishes_active_write_cancels_queue_and_discards_delivery(qtbot, qapp) -> None:
    parent = QObject()
    worker = BackgroundWorker(parent, "test-shutdown")
    started, release = Event(), Event()
    writes, results = [], []

    def write():
        started.set()
        assert release.wait(5)
        writes.append("saved")

    timer = Timer(0.05, release.set)
    try:
        worker.submit(write, results.append)
        qtbot.waitUntil(started.is_set)
        worker.submit(lambda: writes.append("queued"), results.append)
        timer.start()
        worker.shutdown()
        qapp.processEvents()
        assert writes == ["saved"]
        assert results == []
        worker.shutdown()
        worker.submit(lambda: writes.append("after close"), results.append)
        qapp.processEvents()
        assert writes == ["saved"]
        assert results == []
    finally:
        release.set()
        timer.cancel()
        worker.shutdown()
