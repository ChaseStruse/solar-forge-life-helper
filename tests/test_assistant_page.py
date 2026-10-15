"""Member-facing assistant setup stays opt-in and visibly scoped."""

from datetime import date, datetime, time, timedelta

from PySide6.QtCore import Qt

from solar_forge_desktop.assistant_settings import AssistantSettingsStore
from solar_forge_desktop.configuration import SettingsStore
from solar_forge_desktop.storage import Storage
from solar_forge_desktop.tasks import TaskService
from solar_forge_desktop.window import TaskWindow


def test_member_can_enable_ask_and_disable_assistant(qtbot, monkeypatch, tmp_path) -> None:
    storage = Storage(tmp_path / "family.db")
    profile = storage.default_profile_id()
    TaskService(storage).add_task(
        profile, "Water plants", due_at=datetime.combine(date.today() + timedelta(days=2),
                                                          time(9)),
    )
    settings = SettingsStore(tmp_path / "config")
    window = TaskWindow(TaskService(storage), profile, storage.close,
                        settings_store=settings, data_directory=tmp_path)
    qtbot.addWidget(window)
    window.show()
    window.show_assistant()
    page = window.assistant_page
    store = AssistantSettingsStore(settings.path.parent)
    assert window.pages.currentWidget() is page
    assert not store.load(profile).enabled

    page.model.setCurrentText("local-model")
    page.tasks.setChecked(True)
    qtbot.mouseClick(page.enable_button, Qt.MouseButton.LeftButton)
    assert store.load(profile).enabled
    assert not store.load(profile).include_calendar

    prompts = []

    class FakeClient:
        def __init__(self, _settings):
            pass

        def ask(self, system, user):
            prompts.append(user)
            return "Water the plants on Friday."

    monkeypatch.setattr("solar_forge_desktop.assistant.LocalModelClient", FakeClient)
    page.question.setText("What needs doing?")
    qtbot.mouseClick(page.ask_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: "Water the plants" in page.answer.toPlainText())
    assert "Water plants" in prompts[0]
    assert "Water plants" in page.records.toPlainText()

    page.calendar.setChecked(True)
    qtbot.mouseClick(page.ask_button, Qt.MouseButton.LeftButton)
    assert "Save your permission" in page.status.text()
    assert len(prompts) == 1
    qtbot.mouseClick(page.disable_button, Qt.MouseButton.LeftButton)
    assert not store.load(profile).enabled
    assert not page.answer.toPlainText()
    assert not page.records.toPlainText()
    window.close()
