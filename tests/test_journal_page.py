"""Qt interactions for the desktop Easy Journal page."""

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QBoxLayout, QDialog, QPushButton

from solar_forge_desktop.journal import JournalService
from solar_forge_desktop.storage import Storage
from solar_forge_desktop.tasks import TaskService
from solar_forge_desktop.window import TaskWindow


def _button(card, name: str) -> QPushButton:
    return next(
        button for button in card.findChildren(QPushButton)
        if button.accessibleName() == name
    )


def _active_dialog(page) -> QDialog:
    return page.findChildren(QDialog, "journalDeleteDialog")[-1]


def test_journal_navigation_create_edit_delete_and_restart(qtbot, tmp_path: Path) -> None:
    path = tmp_path / "solar-forge.db"
    storage = Storage(path)
    profile = storage.default_profile_id()
    window = TaskWindow(TaskService(storage), profile, storage.close)
    qtbot.addWidget(window)
    window.show()
    card = next(
        item for item in window.findChildren(QPushButton, "appCard")
        if item.accessibleName() == "Open Easy Journal"
    )
    qtbot.mouseClick(card, Qt.MouseButton.LeftButton)
    page = window.journal_page
    assert window.pages.currentIndex() == 3
    assert window.journal_nav.isChecked()
    window.resize(800, 600)
    qtbot.waitUntil(
        lambda: page.columns.direction() == QBoxLayout.Direction.TopToBottom
    )
    window.resize(1280, 800)
    qtbot.waitUntil(lambda: page.timeline_heading.text() == "Memory Timeline (0)")
    qtbot.waitUntil(page.save_button.isEnabled)
    page.title_input.setText("  My day  ")
    literal_content = "<b>First line</b>\nSecond line &amp; <script>text</script>"
    page.content_input.setPlainText(f"  {literal_content}  ")
    qtbot.mouseClick(page.save_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: page.timeline_heading.text() == "Memory Timeline (1)")
    assert page.status.text() == "Journal entry saved successfully!"
    assert page.title_input.text() == ""
    entry = JournalService(storage).list_entries(profile)[0]
    assert (entry.title, entry.content) == ("My day", literal_content)

    card = page.timeline_layout.itemAt(0).widget()
    qtbot.mouseClick(_button(card, "Expand My day"), Qt.MouseButton.LeftButton)
    assert "Second line" in card.findChild(type(page.timeline_heading), "journalBodyText").text()
    qtbot.mouseClick(_button(card, "Edit My day"), Qt.MouseButton.LeftButton)
    editor = page.timeline_layout.itemAt(0).widget()
    cancel_edit = next(
        button for button in editor.findChildren(QPushButton) if button.text() == "Cancel"
    )
    qtbot.mouseClick(cancel_edit, Qt.MouseButton.LeftButton)
    assert JournalService(storage).list_entries(profile)[0].title == "My day"
    qtbot.mouseClick(
        _button(page.timeline_layout.itemAt(0).widget(), "Edit My day"),
        Qt.MouseButton.LeftButton,
    )
    editor = page.timeline_layout.itemAt(0).widget()
    editor.findChild(type(page.title_input), "journalInput").setText("Updated day")
    content_editor = editor.findChild(type(page.content_input), "journalInput")
    assert content_editor.toPlainText() == literal_content
    assert not content_editor.acceptRichText()
    assert not page.content_input.acceptRichText()
    content_editor.setPlainText("Updated thoughts")
    save = next(
        button for button in editor.findChildren(QPushButton)
        if button.text() == "Save Changes"
    )
    qtbot.mouseClick(save, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: JournalService(storage).list_entries(profile)[0].title == "Updated day")
    qtbot.waitUntil(lambda: page.status.text() == "Journal entry updated.")
    assert JournalService(storage).list_entries(profile)[0].created_at == entry.created_at
    qtbot.waitUntil(
        lambda: page.timeline_layout.itemAt(0).widget().accessibleName()
        == "Journal entry Updated day"
    )

    card = page.timeline_layout.itemAt(0).widget()
    QTimer.singleShot(
        0,
        lambda: next(
            button for button in _active_dialog(page).findChildren(QPushButton)
            if button.text() == "Cancel"
        ).click(),
    )
    qtbot.mouseClick(_button(card, "Delete Updated day"), Qt.MouseButton.LeftButton)
    assert len(JournalService(storage).list_entries(profile)) == 1
    QTimer.singleShot(
        0,
        lambda: _active_dialog(page).findChild(
            QPushButton, "journalConfirmDelete"
        ).click(),
    )
    qtbot.mouseClick(_button(card, "Delete Updated day"), Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: page.timeline_heading.text() == "Memory Timeline (0)")
    assert JournalService(storage).list_entries(profile) == ()

    page.title_input.setText("Keep me")
    page.content_input.setPlainText("Persisted")
    qtbot.mouseClick(page.save_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: page.timeline_heading.text() == "Memory Timeline (1)")
    window.close()
    reopened = Storage(path)
    assert JournalService(reopened).list_entries(profile)[0].content == "Persisted"
    reopened.close()


def test_journal_validation_and_search_navigation(qtbot, tmp_path: Path) -> None:
    storage = Storage(tmp_path / "solar-forge.db")
    profile = storage.default_profile_id()
    window = TaskWindow(TaskService(storage), profile, storage.close)
    qtbot.addWidget(window)
    window.show()
    window.app_search.setText("journal")
    window.app_search.returnPressed.emit()
    page = window.journal_page
    assert window.pages.currentIndex() == 3
    qtbot.waitUntil(page.save_button.isEnabled)
    qtbot.mouseClick(page.save_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: page.status.text() == "Journal title is required.")
    page.title_input.setText("Title")
    qtbot.mouseClick(page.save_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: page.status.text() == "Journal entry content is required.")
    page.content_input.setPlainText("Text")
    qtbot.mouseClick(page.save_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: page.timeline_heading.text() == "Memory Timeline (1)")
    card = page.timeline_layout.itemAt(0).widget()
    qtbot.mouseClick(_button(card, "Edit Title"), Qt.MouseButton.LeftButton)
    editor = page.timeline_layout.itemAt(0).widget()
    editor.findChild(type(page.title_input), "journalInput").clear()
    save = next(
        button for button in editor.findChildren(QPushButton)
        if button.text() == "Save Changes"
    )
    qtbot.mouseClick(save, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: page.status.text() == "Journal title is required.")
    assert JournalService(storage).list_entries(profile)[0].title == "Title"
    window.close()
