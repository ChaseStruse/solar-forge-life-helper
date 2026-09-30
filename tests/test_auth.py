import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from PySide6.QtCore import Qt

from solar_forge_desktop.__main__ import DesktopSession
from solar_forge_desktop.auth import AuthService
from solar_forge_desktop.storage import Profile, Storage
from solar_forge_desktop.tasks import TaskService


def test_register_claims_existing_home_tasks_and_login_survives_restart(tmp_path: Path) -> None:
    path = tmp_path / "solar-forge.db"
    storage = Storage(path)
    home = storage.default_profile_id()
    TaskService(storage).add_task(home, "Keep my task")
    auth = AuthService(storage)
    assert not auth.has_accounts()
    assert auth.register("  Alice  ", "secret pass") == home
    assert auth.has_accounts()
    assert auth.login("ALICE", "secret pass") == home
    with storage.sessions() as session:
        profile = session.get(Profile, home)
        assert profile.password_hash != "secret pass"
        assert "secret pass" not in profile.password_hash
    storage.close()
    reopened = Storage(path)
    assert AuthService(reopened).login("alice", "secret pass") == home
    assert [t.title for t in TaskService(reopened).list_tasks(home)[0]] == ["Keep my task"]
    reopened.close()


def test_accounts_validate_and_keep_tasks_isolated(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "solar-forge.db")
    auth = AuthService(storage)
    for username, password, message in [
        ("a!", "long enough", "3–80"),
        ("alice", "short", "at least 8"),
    ]:
        with pytest.raises(ValueError, match=message):
            auth.register(username, password)
    alice = auth.register("alice", "long enough")
    with pytest.raises(ValueError, match="already taken"):
        auth.register("ALICE", "long enough")
    bob = auth.register("bob", "another password")
    for username, password in [("missing", "long enough"), ("alice", "wrong password")]:
        with pytest.raises(ValueError, match="Invalid username or password"):
            auth.login(username, password)
    task_id = TaskService(storage).add_task(alice, "Only Alice")
    assert TaskService(storage).list_tasks(bob) == ([], [])
    with pytest.raises(ValueError, match="Task not found"):
        TaskService(storage).delete_task(bob, task_id)
    assert auth.login("bob", "another password") == bob
    storage.close()


def test_corrupt_password_hash_never_authenticates(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "solar-forge.db")
    auth = AuthService(storage)
    profile_id = auth.register("alice", "long enough")
    for damaged_hash in (None, "other$00$00", "scrypt:16384:8:1$00$00", "broken"):
        with storage.sessions.begin() as session:
            session.get(Profile, profile_id).password_hash = damaged_hash
        with pytest.raises(ValueError, match="Invalid username or password"):
            auth.login("alice", "long enough")
    storage.close()


def test_v1_upgrade_keeps_snapshot_and_existing_tasks(tmp_path: Path) -> None:
    path = tmp_path / "old.db"
    with closing(sqlite3.connect(path)) as db:
        db.executescript("""
            CREATE TABLE profiles (id INTEGER PRIMARY KEY, name VARCHAR(100) NOT NULL);
            CREATE TABLE tasks (id INTEGER PRIMARY KEY, profile_id INTEGER NOT NULL,
                title VARCHAR(200) NOT NULL, completed BOOLEAN NOT NULL,
                created_at VARCHAR(40) NOT NULL, completed_at VARCHAR(40),
                FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE);
            INSERT INTO profiles VALUES (1, 'Home');
            INSERT INTO tasks VALUES (1, 1, 'Old task', 0, '2026-01-01T00:00:00+00:00', NULL);
            PRAGMA user_version=1;
        """)
    storage = Storage(path)
    assert [t.title for t in TaskService(storage).list_tasks(1)[0]] == ["Old task"]
    assert AuthService(storage).register("alice", "long enough") == 1
    storage.close()
    snapshot = path.with_name("old.db.pre-auth-v1")
    with closing(sqlite3.connect(snapshot)) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 1
        assert db.execute("SELECT title FROM tasks").fetchone()[0] == "Old task"
        assert "username" not in [r[1] for r in db.execute("PRAGMA table_info(profiles)")]
    with closing(sqlite3.connect(path)) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 14
    with closing(sqlite3.connect(path.with_name("old.db.pre-budget-v2"))) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 2


def test_auth_window_signup_login_and_signout(qtbot, tmp_path: Path) -> None:
    storage = Storage(tmp_path / "solar-forge.db")
    session = DesktopSession(storage)
    auth = session.auth_window
    qtbot.addWidget(auth)
    auth.show()
    assert auth.heading.text() == "Create your account"
    assert auth.password.echoMode() == auth.password.EchoMode.Password
    qtbot.keyClicks(auth.username, "alice")
    qtbot.keyClicks(auth.password, "short")
    qtbot.mouseClick(auth.submit_button, Qt.MouseButton.LeftButton)
    assert "at least 8" in auth.error.text()
    auth.password.setText("long enough")
    qtbot.mouseClick(auth.submit_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: session.task_window is not None)
    workspace = session.task_window
    qtbot.addWidget(workspace)
    assert workspace.isVisible()
    assert "alice" in workspace.pages.widget(0).findChild(type(auth.heading), "heading").text()
    qtbot.mouseClick(
        workspace.findChild(type(auth.submit_button), "signOut"), Qt.MouseButton.LeftButton
    )
    login = session.auth_window
    qtbot.addWidget(login)
    assert login.heading.text() == "Welcome back"
    assert not workspace.isVisible()
    login.username.setText("alice")
    login.password.setText("wrong password")
    qtbot.mouseClick(login.submit_button, Qt.MouseButton.LeftButton)
    assert login.error.text() == "Invalid username or password."
    login.password.setText("long enough")
    qtbot.keyClick(login.password, Qt.Key.Key_Return)
    qtbot.waitUntil(lambda: session.task_window is not None)
    assert session.task_window.isVisible()
    session.task_window.close()
    storage.close()


def test_enter_signup_keeps_line_edit_alive_until_key_event_finishes(
    qtbot, tmp_path: Path,
) -> None:
    storage = Storage(tmp_path / "solar-forge.db")
    session = DesktopSession(storage)
    session.auth_window.username.setText("alice")
    session.auth_window.password.setText("long enough")
    qtbot.keyClick(session.auth_window.password, Qt.Key.Key_Return)
    qtbot.waitUntil(lambda: session.task_window is not None)
    assert session.task_window.isVisible()
    session.task_window.close()
    storage.close()
