from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QCheckBox, QDialog, QFrame, QLabel, QPushButton

from solar_forge_desktop.configuration import SettingsStore
from solar_forge_desktop.reminders import DueReminder
from solar_forge_desktop.settings_dialog import StorageSettingsDialog
from solar_forge_desktop.storage import Storage
from solar_forge_desktop.tasks import TaskService
from solar_forge_desktop.window import DeleteTaskDialog, TaskWindow


def test_reminder_banner_opens_calendar(qtbot, tmp_path: Path) -> None:
    storage = Storage(tmp_path / "solar-forge.db")
    window = TaskWindow(TaskService(storage), storage.default_profile_id(), storage.close)
    qtbot.addWidget(window)
    window.show()
    due = datetime(2026, 10, 1, 22, 30, tzinfo=timezone.utc)
    window._on_reminders((DueReminder(1, 1, "Dentist", due, due),))
    assert window.reminder_button.isVisible()
    assert "Dentist" in window.reminder_button.text()

    qtbot.mouseClick(window.reminder_button, Qt.MouseButton.LeftButton)

    assert window.pages.currentWidget() is window.calendar_page
    assert not window.reminder_button.isVisible()
    window.close()


def test_storage_selectors_follow_window_theme(qtbot, monkeypatch, tmp_path: Path) -> None:
    storage = Storage(tmp_path / "solar-forge.db")
    window = TaskWindow(
        TaskService(storage), storage.default_profile_id(), storage.close,
        settings_store=SettingsStore(tmp_path / "config"), data_directory=tmp_path / "data",
    )
    qtbot.addWidget(window)
    window._set_theme("Ocean Blue")
    styles = []
    monkeypatch.setattr(StorageSettingsDialog, "exec", lambda dialog: styles.append(
        dialog.styleSheet()
    ))

    window.show_storage_settings()

    assert "#133e68" in styles[0]
    assert "#8b5cf6" not in styles[0]
    window.close()


def test_task_window_creates_completes_and_deletes(qtbot, monkeypatch, tmp_path: Path) -> None:
    storage = Storage(tmp_path / "solar-forge.db")
    profile = storage.default_profile_id()
    window = TaskWindow(TaskService(storage), profile, storage.close)
    qtbot.addWidget(window)
    window.show()
    assert window.pages.currentIndex() == 0
    assert window.pages.widget(0).findChild(QLabel, "heading").text() == "Welcome back, Home"
    task_card = next(
        card for card in window.findChildren(QPushButton, "appCard")
        if card.accessibleName() == "Open Task List"
    )
    qtbot.mouseClick(task_card, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: window.active_heading.text() == "Active Tasks (0)")
    assert window.pages.currentIndex() == 1
    assert window.active_card.geometry().x() < window.completed_card.geometry().x()
    assert window.findChild(QFrame, "sidebar").width() == 280
    assert "No active tasks" in window.active_card.findChild(QLabel, "muted").text()

    qtbot.keyClicks(window.title_input, "Write a note")
    qtbot.mouseClick(window.add_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: window.active_heading.text() == "Active Tasks (1)")
    assert window.title_input.text() == ""
    task_id = TaskService(storage).list_tasks(profile)[0][0].id
    task_title = window.active_card.findChild(QLabel, "taskTitleText")
    assert task_title.text() == "Write a note"
    title_image = task_title.grab().toImage()
    assert any(
        all(channel > 180 for channel in title_image.pixelColor(x, y).getRgb()[:3])
        for y in range(title_image.height())
        for x in range(title_image.width())
    )
    qtbot.waitUntil(
        lambda: (
            (candidate := window.findChild(QCheckBox, f"taskCheck_{task_id}")) is not None
            and candidate.isVisible()
            and candidate.width() >= 20
        )
    )
    check = window.findChild(QCheckBox, f"taskCheck_{task_id}")
    indicator = check.grab().toImage()
    assert any(
        indicator.pixelColor(x, y).name() == "#8b5cf6"
        for y in range(indicator.height())
        for x in range(indicator.width())
    )
    qtbot.mouseClick(check, Qt.MouseButton.LeftButton, pos=QPoint(9, check.height() // 2))
    qtbot.waitUntil(lambda: window.completed_heading.text() == "Completed Tasks (1)")
    assert window.completed_card.findChild(QLabel, "completedTitle").text() == "Write a note"
    checked = window.findChild(QCheckBox, f"taskCheck_{task_id}")
    checked_image = checked.grab().toImage()
    assert any(
        checked_image.pixelColor(x, y).name() == "#10b981"
        for y in range(checked_image.height())
        for x in range(checked_image.width())
    )
    assert window.completed_card.findChild(QLabel, "completionTime").text().startswith(
        "Completed at "
    )

    monkeypatch.setattr(
        DeleteTaskDialog, "exec", lambda _dialog: QDialog.DialogCode.Accepted
    )
    delete = window.findChild(QPushButton, f"taskDelete_{task_id}")
    qtbot.mouseClick(delete, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: window.completed_heading.text() == "Completed Tasks (0)")
    window.close()
    reopened = Storage(tmp_path / "solar-forge.db")
    assert TaskService(reopened).list_tasks(profile) == ([], [])
    reopened.close()


def test_task_sharing_controls_and_member_view(qtbot, tmp_path: Path) -> None:
    storage = Storage(tmp_path / "solar-forge.db")
    owner = storage.default_profile_id()
    member = storage.create_profile("Member")
    service = TaskService(storage)
    window = TaskWindow(service, owner, lambda: None)
    qtbot.addWidget(window)
    window.show()
    window.show_tasks()
    qtbot.waitUntil(lambda: window.active_heading.text() == "Active Tasks (0)")
    window.title_input.setText("Family errand")
    window.task_visibility.setCurrentIndex(window.task_visibility.findData("household"))
    qtbot.mouseClick(window.add_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: window.active_heading.text() == "Active Tasks (1)")
    task = service.list_tasks(owner)[0][0]
    assert task.visibility == "household"
    assert window.task_visibility.currentData() == "private"
    sharing = window.findChild(QPushButton, f"taskVisibility_{task.id}")
    assert sharing.text() == "Household"
    window.close()

    member_window = TaskWindow(service, member, lambda: None)
    qtbot.addWidget(member_window)
    member_window.show()
    member_window.show_tasks()
    qtbot.waitUntil(lambda: member_window.active_heading.text() == "Active Tasks (1)")
    assert member_window.findChild(QPushButton, f"taskDelete_{task.id}") is None
    assert member_window.findChild(QPushButton, f"taskVisibility_{task.id}") is None
    member_window.close()
    storage.close()


def test_delete_dialog_uses_solar_forge_colors_and_requires_confirmation(qtbot) -> None:
    dialog = DeleteTaskDialog("<b>Sample</b>", None)
    qtbot.addWidget(dialog)
    dialog.show()
    assert dialog.findChild(QLabel, "deleteMessage").text() == (
        "Delete '<b>Sample</b>'? This can't be undone."
    )
    assert dialog.findChild(QLabel, "deleteMessage").textFormat() == Qt.TextFormat.PlainText
    assert dialog.grab().toImage().pixelColor(8, 8).name() == "#1a1533"
    cancel = dialog.findChild(QPushButton, "cancelDelete")
    assert cancel.isDefault()
    qtbot.mouseClick(cancel, Qt.MouseButton.LeftButton)
    assert dialog.result() == QDialog.DialogCode.Rejected

    confirm_dialog = DeleteTaskDialog("Sample", None)
    qtbot.addWidget(confirm_dialog)
    confirm_dialog.show()
    qtbot.mouseClick(
        confirm_dialog.findChild(QPushButton, "confirmDelete"), Qt.MouseButton.LeftButton
    )
    assert confirm_dialog.result() == QDialog.DialogCode.Accepted


def test_empty_title_shows_feedback(qtbot, tmp_path: Path) -> None:
    storage = Storage(tmp_path / "solar-forge.db")
    window = TaskWindow(TaskService(storage), storage.default_profile_id(), storage.close)
    qtbot.addWidget(window)
    window.show()
    qtbot.mouseClick(window.tasks_nav, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: window.active_heading.text() == "Active Tasks (0)")
    qtbot.mouseClick(window.add_button, Qt.MouseButton.LeftButton)
    assert window.status.text() == "Task title is required."
    window.close()


def test_dashboard_navigation_uses_profile_name(qtbot, tmp_path: Path) -> None:
    storage = Storage(tmp_path / "solar-forge.db")
    profile_id = storage.create_profile("Alex")
    window = TaskWindow(TaskService(storage), profile_id, storage.close,
                        profile_name=storage.profile_name(profile_id))
    qtbot.addWidget(window)
    window.show()
    assert window.pages.currentIndex() == 0
    assert window.pages.widget(0).findChild(QLabel, "heading").text() == "Welcome back, Alex"
    assert window.dashboard_nav.isChecked()
    qtbot.mouseClick(window.tasks_nav, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: window.active_heading.text() == "Active Tasks (0)")
    assert window.pages.currentIndex() == 1
    assert window.tasks_nav.isChecked()
    qtbot.mouseClick(window.dashboard_nav, Qt.MouseButton.LeftButton)
    assert window.pages.currentIndex() == 0
    assert window.dashboard_nav.isChecked()
    window.close()


def test_dashboard_cards_stack_scroll_and_keep_navigation_exclusive(qtbot, tmp_path: Path) -> None:
    from PySide6.QtWidgets import QScrollArea

    storage = Storage(tmp_path / "solar-forge.db")
    window = TaskWindow(TaskService(storage), storage.default_profile_id(), storage.close)
    qtbot.addWidget(window)
    window.resize(690, 500)
    window.show()
    scroll = window.findChild(QScrollArea, "dashboardScroll")
    qtbot.waitUntil(lambda: scroll.verticalScrollBar().maximum() > 0)
    positions = [window.app_grid.getItemPosition(i) for i in range(7)]
    assert [position[1] for position in positions] == [0, 0, 0, 0, 0, 0, 0]
    assert scroll.horizontalScrollBar().maximum() == 0
    for card, index in zip(window.app_cards, (2, 1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12), strict=True):
        window.show_dashboard()
        scroll.ensureWidgetVisible(card)
        qtbot.mouseClick(card, Qt.MouseButton.LeftButton)
        assert window.pages.currentIndex() == index
        nav = (window.dashboard_nav, window.tasks_nav, window.budget_nav,
               window.journal_nav, window.medicine_nav, window.habit_nav,
               window.calorie_nav, window.weight_nav, window.workout_nav,
               window.pet_nav, window.meal_nav, window.maintenance_nav, window.calendar_nav)
        assert [button.isChecked() for button in nav] == [i == index for i in range(13)]
    window.show_dashboard()
    window.resize(1280, 800)
    qtbot.waitUntil(lambda: window._app_columns == 4)
    assert [window.app_grid.getItemPosition(i)[1] for i in range(8)] == [
        0, 1, 2, 3, 0, 1, 2, 3,
    ]
    assert all(card.height() == 136 for card in window.app_cards)
    assert scroll.horizontalScrollBar().maximum() == 0
    window.resize(1600, 900)
    qtbot.waitUntil(lambda: window._app_columns == 5)
    window.resize(1920, 900)
    qtbot.waitUntil(lambda: window._app_columns == 6)
    assert [window.app_grid.getItemPosition(i)[1] for i in range(7)] == [
        0, 1, 2, 3, 4, 5, 0,
    ]
    assert scroll.horizontalScrollBar().maximum() == 0
    window.resize(690, 500)
    qtbot.waitUntil(lambda: window._app_columns == 1)
    window.close()
