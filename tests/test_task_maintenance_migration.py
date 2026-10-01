"""Existing records survive the reminder schema upgrade without gaining rules."""

import sqlite3
from contextlib import closing
from datetime import date

from solar_forge_desktop.maintenance import MaintenanceService
from solar_forge_desktop.storage import Storage
from solar_forge_desktop.tasks import TaskService


def test_v17_upgrade_preserves_records_and_snapshots(tmp_path):
    path = tmp_path / "family.db"
    storage = Storage(path)
    profile_id = storage.default_profile_id()
    task_id = TaskService(storage).add_task(profile_id, "Keep task")
    item_id = MaintenanceService(storage).add(
        profile_id, "Keep filter", "General", date(2026, 11, 1), 1, "months",
    )
    storage.close()
    with closing(sqlite3.connect(path)) as db:
        for table in ("task_reminder_deliveries", "task_reminders",
                      "maintenance_reminder_deliveries", "maintenance_reminders"):
            db.execute(f"DROP TABLE {table}")
        db.execute("PRAGMA foreign_keys=OFF")
        db.execute("ALTER TABLE tasks DROP COLUMN due_at")
        db.execute("PRAGMA user_version=17")
        db.commit()
    upgraded = Storage(path)
    tasks, _ = TaskService(upgraded).list_tasks(profile_id)
    assert [(task.id, task.title) for task in tasks] == [(task_id, "Keep task")]
    assert MaintenanceService(upgraded).view(profile_id).items[0].id == item_id
    upgraded.close()
    with closing(sqlite3.connect(path)) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 18
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        assert db.execute("SELECT count(*) FROM task_reminders").fetchone()[0] == 0
    snapshot = path.with_name("family.db.pre-task-maintenance-reminders-v17")
    with closing(sqlite3.connect(snapshot)) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 17
