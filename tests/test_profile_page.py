"""Qt Profile navigation, editing, validation, and restart interaction."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QBoxLayout, QLabel

from solar_forge_desktop.profile import ProfileService
from solar_forge_desktop.storage import Storage
from solar_forge_desktop.tasks import TaskService
from solar_forge_desktop.window import TaskWindow


def test_profile_page_saves_details_and_updates_shell(qtbot, tmp_path: Path) -> None:
    path = tmp_path / "solar-forge.db"
    storage = Storage(path)
    profile = storage.default_profile_id()
    window = TaskWindow(TaskService(storage), profile, storage.close)
    qtbot.addWidget(window)
    window.resize(1280, 800)
    window.show()
    qtbot.mouseClick(window.profile_button, Qt.MouseButton.LeftButton)
    page = window.profile_page
    qtbot.waitUntil(lambda: page.summary_name.text() == "Home")
    assert window.pages.currentIndex() == 13
    assert page.findChild(QLabel, "profileTitle").text() == "Solar Forge Profile"
    assert page.summary_bio.text() == "“Solar Forge Life Helper member”"
    page.name_input.setText("Alex")
    page.bio_input.setPlainText("Make time for rest")
    page.color_input.setCurrentIndex(page.color_input.findData("#10b981"))
    page.icon_input.setCurrentIndex(page.icon_input.findData("🚀"))
    qtbot.mouseClick(page.save_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: page.status.text() ==
                    "Profile and preferences updated successfully!")
    assert page.summary_name.text() == "Alex"
    assert page.summary_bio.text() == "“Make time for rest”"
    assert window.profile_button.text() == "🚀"
    assert window.sidebar_profile.text().endswith("Alex")
    window.show_dashboard()
    assert window.pages.widget(0).findChild(QLabel, "heading").text() == "Welcome back, Alex"
    window.close()

    reopened = Storage(path)
    saved = ProfileService(reopened).view(profile)
    assert (saved.name, saved.bio, saved.avatar_color, saved.avatar_emoji) == (
        "Alex", "Make time for rest", "#10b981", "🚀"
    )
    reopened.close()


def test_profile_page_validation_and_small_layout(qtbot, tmp_path: Path) -> None:
    storage = Storage(tmp_path / "solar-forge.db")
    profile = storage.default_profile_id()
    window = TaskWindow(TaskService(storage), profile, storage.close)
    qtbot.addWidget(window)
    window.resize(690, 500)
    window.show()
    window.show_profile()
    page = window.profile_page
    qtbot.waitUntil(lambda: page.summary_name.text() == "Home")
    assert page.columns.direction() == QBoxLayout.Direction.TopToBottom
    page.name_input.clear()
    qtbot.mouseClick(page.save_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: page.status.text() == "Name cannot be empty.")
    assert ProfileService(storage).view(profile).name == "Home"
    window.close()
