"""Household migration keeps old records private and local accounts joined."""

import sqlite3
from contextlib import closing
from pathlib import Path

from sqlalchemy import select

from solar_forge_desktop.auth import AuthService
from solar_forge_desktop.storage import HouseholdMember, Storage
from solar_forge_desktop.tasks import TaskService


def test_local_accounts_join_one_household_without_sharing_tasks(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "family.db")
    auth = AuthService(storage)
    owner = auth.register("parent", "secret-password")
    member = auth.register("child", "another-password")
    task = TaskService(storage).add_task(owner, "Private task")
    with storage.sessions() as session:
        memberships = session.scalars(select(HouseholdMember).order_by(
            HouseholdMember.profile_id
        )).all()
        assert [item.profile_id for item in memberships] == [owner, member]
        assert [item.role for item in memberships] == ["owner", "member"]
        assert memberships[0].household_id == memberships[1].household_id
    assert [item.id for item in TaskService(storage).list_tasks(owner)[0]] == [task]
    assert TaskService(storage).list_tasks(member) == ([], [])
    storage.close()


def test_v14_upgrade_defaults_existing_tasks_to_private(tmp_path: Path) -> None:
    path = tmp_path / "family.db"
    storage = Storage(path)
    owner = storage.default_profile_id()
    task = TaskService(storage).add_task(owner, "Keep private")
    storage.close()
    with closing(sqlite3.connect(path)) as db:
        db.execute("DROP TABLE household_members")
        db.execute("DROP TABLE households")
        db.execute("ALTER TABLE tasks DROP COLUMN visibility")
        db.execute("ALTER TABLE calendar_events DROP COLUMN visibility")
        db.execute("PRAGMA user_version=14")
        db.commit()

    upgraded = Storage(path)
    assert [item.id for item in TaskService(upgraded).list_tasks(owner)[0]] == [task]
    upgraded.close()
    with closing(sqlite3.connect(path)) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 15
        assert db.execute("SELECT visibility FROM tasks WHERE id=?", (task,)).fetchone() == (
            "private",)
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    with closing(sqlite3.connect(path.with_name("family.db.pre-household-v14"))) as snapshot:
        assert snapshot.execute("PRAGMA user_version").fetchone()[0] == 14
