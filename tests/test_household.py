"""Household migration keeps old records private and local accounts joined."""

import sqlite3
from contextlib import closing
from datetime import date, datetime
from pathlib import Path

import pytest
from sqlalchemy import select

from solar_forge_desktop.auth import AuthService
from solar_forge_desktop.calendar import CalendarService
from solar_forge_desktop.storage import Household, HouseholdMember, Storage
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
        db.execute("DROP TABLE calendar_reminder_deliveries")
        db.execute("DROP TABLE calendar_reminders")
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
        assert db.execute("PRAGMA user_version").fetchone()[0] == 17
        assert db.execute("SELECT visibility FROM tasks WHERE id=?", (task,)).fetchone() == (
            "private",)
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    with closing(sqlite3.connect(path.with_name("family.db.pre-household-v14"))) as snapshot:
        assert snapshot.execute("PRAGMA user_version").fetchone()[0] == 14


def test_shared_tasks_and_events_require_same_household(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "family.db")
    owner = storage.default_profile_id()
    member = storage.create_profile("Member")
    outsider = storage.create_profile("Outsider")
    with storage.sessions.begin() as session:
        other_household = Household(name="Other household")
        session.add(other_household)
        session.flush()
        membership = session.scalar(select(HouseholdMember).where(
            HouseholdMember.profile_id == outsider
        ))
        membership.household_id = other_household.id
    tasks = TaskService(storage)
    private_task = tasks.add_task(owner, "Private")
    shared_task = tasks.add_task(owner, "Shared", visibility="household")
    assert [item.id for item in tasks.list_tasks(member)[0]] == [shared_task]
    assert tasks.list_tasks(outsider) == ([], [])
    tasks.toggle_task(member, shared_task)
    with pytest.raises(ValueError, match="not found"):
        tasks.toggle_task(member, private_task)
    with pytest.raises(ValueError, match="not found"):
        tasks.delete_task(member, shared_task)
    with pytest.raises(ValueError, match="not found"):
        tasks.set_visibility(member, shared_task, "private")

    calendar = CalendarService(storage)
    start = datetime(2026, 10, 1, 9)
    end = datetime(2026, 10, 1, 10)
    private_event = calendar.save(owner, "Private", None, "Home", start, end)
    shared_event = calendar.save(
        owner, "Shared", None, "Home", start, end, visibility="household"
    )
    assert calendar.view(member, date(2026, 10, 1)).event_count == 1
    assert calendar.view(outsider, date(2026, 10, 1)).event_count == 0
    assert calendar.get(member, shared_event).visibility == "household"
    with pytest.raises(ValueError, match="not found"):
        calendar.get(member, private_event)
    with pytest.raises(ValueError, match="not found"):
        calendar.delete(member, shared_event)
    calendar.save(member, "Updated", None, "Home", start, end, event_id=shared_event)
    assert calendar.get(owner, shared_event).title == "Updated"
    with pytest.raises(ValueError, match="Only the owner"):
        calendar.save(
            member, "Hidden", None, "Home", start, end,
            event_id=shared_event, visibility="private",
        )
    storage.close()
