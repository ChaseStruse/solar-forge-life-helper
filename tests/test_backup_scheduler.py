"""Scheduled backups run when due and remain off by default."""

from pathlib import Path

from PySide6.QtWidgets import QApplication

from solar_forge_desktop.backup_scheduler import BackupScheduler
from solar_forge_desktop.backups import latest_backup
from solar_forge_desktop.configuration import DATABASE_NAME, AppSettings, SettingsStore
from solar_forge_desktop.storage import Storage


def test_due_schedule_runs_once_and_respects_off(qtbot, tmp_path: Path) -> None:
    data = tmp_path / "data"
    storage = Storage(data / DATABASE_NAME)
    storage.create_profile("Family")
    folder = tmp_path / "backups"
    store = SettingsStore(tmp_path / "config")
    store.save(AppSettings(data, folder, backup_schedule="daily", backup_retention=2))
    scheduler = BackupScheduler(store, data, QApplication.instance())
    scheduler.start()
    qtbot.waitUntil(lambda: scheduler.last_result is not None, timeout=10000)
    assert scheduler.last_result.startswith("Scheduled backup saved")
    first = latest_backup(folder)
    scheduler.check()
    qtbot.wait(100)
    assert latest_backup(folder) == first

    store.save(AppSettings(data, folder, backup_schedule="off"))
    scheduler.check()
    qtbot.wait(100)
    assert latest_backup(folder) == first
    scheduler.shutdown()
    storage.close()
