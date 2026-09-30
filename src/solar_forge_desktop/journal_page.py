"""Native Easy Journal page with a bounded, editable memory timeline."""

from datetime import datetime
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QBoxLayout,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from solar_forge_desktop.journal import JournalService
from solar_forge_desktop.storage import JournalItem
from solar_forge_desktop.workers import BackgroundWorker

STYLE = """
QWidget#journalPage, QWidget#journalBody, QWidget#journalTimeline { background: #0a0712; }
QScrollArea#journalScroll { background: #0a0712; border: none; }
QFrame#journalCard { background: #1a1533; border: 1px solid #302943;
    border-radius: 16px; }
QLabel#journalTitle { color: #f3f4f6; font-size: 32px; font-weight: 700; }
QLabel#journalSubtitle, QLabel#journalDate, QLabel#journalEmptyHint {
    color: #a1a1aa; }
QLabel#journalHeading, QLabel#journalEntryTitle { color: #f3f4f6;
    font-size: 18px; font-weight: 700; }
QLabel#journalBodyText { color: #d1d5db; font-size: 14px; }
QLabel#journalStatus { color: #fb7185; }
QLineEdit#journalInput, QTextEdit#journalInput { background: #211b30;
    color: #f3f4f6; border: 1px solid #302943; border-radius: 9px;
    padding: 10px 12px; }
QLineEdit#journalInput:focus, QTextEdit#journalInput:focus { border-color: #8b5cf6; }
QPushButton#journalPrimary { color: white; border: none; border-radius: 10px;
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #8b5cf6,stop:1 #ec4899);
    padding: 10px 14px; font-weight: 700; }
QPushButton#journalSecondary { background: #292143; color: #f3f4f6;
    border: 1px solid #483a64; border-radius: 9px; padding: 8px 12px; }
QPushButton#journalDanger { background: #3a1d39; color: #fb7185;
    border: 1px solid #5b3048; border-radius: 9px; padding: 8px 12px; }
"""


def _label(text: str, name: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName(name)
    label.setWordWrap(True)
    label.setTextFormat(Qt.TextFormat.PlainText)
    return label


class JournalPage(QWidget):
    def __init__(self, service: JournalService, profile_id: int):
        super().__init__()
        self.service = service
        self.profile_id = profile_id
        self._entries: tuple[JournalItem, ...] = ()
        self._editing_id: int | None = None
        self._serial = 0
        self.setObjectName("journalPage")
        self.setStyleSheet(STYLE)
        self._build()
        self._worker = BackgroundWorker(self, "solar-forge-journal")
        self._worker.busy_changed.connect(self._set_busy)
        self._worker.failed.connect(self._show_error)

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setObjectName("journalScroll")
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        body = QWidget()
        body.setObjectName("journalBody")
        scroll.setWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(48, 36, 48, 40)
        layout.setSpacing(16)
        layout.addWidget(_label("Easy Journal", "journalTitle"))
        layout.addWidget(_label(
            "Write daily logs, store thoughts, and keep a personal memory timeline.",
            "journalSubtitle",
        ))
        self.status = _label("", "journalStatus")
        self.status.setAccessibleName("Journal status")
        layout.addWidget(self.status)
        columns = QHBoxLayout()
        self.columns = columns
        columns.setSpacing(28)
        layout.addLayout(columns)
        layout.addStretch()

        form = QFrame()
        form.setObjectName("journalCard")
        form_layout = QVBoxLayout(form)
        form_layout.setContentsMargins(24, 24, 24, 24)
        form_layout.setSpacing(12)
        form_layout.addWidget(_label("New Entry", "journalHeading"))
        form_layout.addWidget(_label("TITLE", "journalDate"))
        self.title_input = QLineEdit()
        self.title_input.setObjectName("journalInput")
        self.title_input.setAccessibleName("Journal title")
        self.title_input.setPlaceholderText("e.g. A productive morning")
        self.title_input.setMaxLength(200)
        form_layout.addWidget(self.title_input)
        form_layout.addWidget(_label("HOW WAS YOUR DAY?", "journalDate"))
        self.content_input = QTextEdit()
        self.content_input.setAcceptRichText(False)
        self.content_input.setObjectName("journalInput")
        self.content_input.setAccessibleName("Journal content")
        self.content_input.setPlaceholderText("Write your thoughts here...")
        self.content_input.setMinimumHeight(200)
        form_layout.addWidget(self.content_input)
        self.save_button = QPushButton("Save Entry")
        self.save_button.setObjectName("journalPrimary")
        self.save_button.setAccessibleName("Save journal entry")
        self.save_button.clicked.connect(self.add_entry)
        form_layout.addWidget(self.save_button)
        columns.addWidget(form, 2, Qt.AlignmentFlag.AlignTop)

        timeline_column = QVBoxLayout()
        timeline_column.setSpacing(12)
        self.timeline_heading = _label("Memory Timeline (0)", "journalHeading")
        timeline_column.addWidget(self.timeline_heading)
        self.timeline = QWidget()
        self.timeline.setObjectName("journalTimeline")
        self.timeline_layout = QVBoxLayout(self.timeline)
        self.timeline_layout.setContentsMargins(0, 0, 0, 0)
        self.timeline_layout.setSpacing(16)
        timeline_column.addWidget(self.timeline)
        timeline_column.addStretch()
        columns.addLayout(timeline_column, 3)
        self._apply_responsive()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_responsive()

    def _apply_responsive(self) -> None:
        self.columns.setDirection(
            QBoxLayout.Direction.TopToBottom if self.width() < 900
            else QBoxLayout.Direction.LeftToRight
        )

    def activate(self) -> None:
        self.refresh()

    def _run(self, action: Callable[[], object], done: Callable[[object], None]) -> None:
        self._worker.submit(action, done)

    def _set_busy(self, busy: bool) -> None:
        self.save_button.setEnabled(not busy)

    def _show_error(self, error: Exception) -> None:
        self.status.setText(
            str(error) if isinstance(error, ValueError) else
            "The journal could not be saved. Please try again."
        )
        self.status.setStyleSheet("color: #fb7185;")

    def refresh(self) -> None:
        self._serial += 1
        serial = self._serial
        self._run(
            lambda: self.service.list_entries(self.profile_id),
            lambda result: self._render(result) if serial == self._serial else None,
        )

    def _render(self, result: object) -> None:
        self._entries = result
        self.timeline_heading.setText(f"Memory Timeline ({len(self._entries)})")
        while self.timeline_layout.count():
            item = self.timeline_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().hide()
                item.widget().deleteLater()
        if not self._entries:
            empty = QFrame()
            empty.setObjectName("journalCard")
            empty_layout = QVBoxLayout(empty)
            empty_layout.setContentsMargins(24, 48, 24, 48)
            title = _label("Your journal is empty.", "journalHeading")
            title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_layout.addWidget(title)
            hint = _label("Record your first entry to start your memory log.", "journalEmptyHint")
            hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_layout.addWidget(hint)
            self.timeline_layout.addWidget(empty)
            return
        for entry in self._entries:
            self.timeline_layout.addWidget(
                self._edit_card(entry) if entry.id == self._editing_id else self._entry_card(entry)
            )

    def _entry_card(self, entry: JournalItem) -> QFrame:
        card = QFrame()
        card.setObjectName("journalCard")
        card.setAccessibleName(f"Journal entry {entry.title}")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)
        header = QHBoxLayout()
        title = QPushButton("▸  " + entry.title)
        title.setObjectName("journalSecondary")
        title.setAccessibleName(f"Expand {entry.title}")
        title.setCheckable(True)
        header.addWidget(title, 1)
        edit = QPushButton("Edit")
        edit.setObjectName("journalSecondary")
        edit.setAccessibleName(f"Edit {entry.title}")
        edit.clicked.connect(lambda _checked=False, item=entry: self._begin_edit(item))
        header.addWidget(edit)
        delete = QPushButton("Delete")
        delete.setObjectName("journalDanger")
        delete.setAccessibleName(f"Delete {entry.title}")
        delete.clicked.connect(lambda _checked=False, item=entry: self._confirm_delete(item))
        header.addWidget(delete)
        layout.addLayout(header)
        created = datetime.fromisoformat(entry.created_at).astimezone()
        date_text = f"Uploaded: {created:%b %d, %Y, %I:%M %p}"
        if entry.updated_at != entry.created_at:
            date_text += "  • Edited"
        layout.addWidget(_label(date_text, "journalDate"))
        content = _label(entry.content, "journalBodyText")
        content.setVisible(False)
        title.toggled.connect(content.setVisible)
        layout.addWidget(content)
        return card

    def _edit_card(self, entry: JournalItem) -> QFrame:
        card = QFrame()
        card.setObjectName("journalCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.addWidget(_label("Edit Entry", "journalHeading"))
        title = QLineEdit(entry.title)
        title.setObjectName("journalInput")
        title.setAccessibleName("Edit journal title")
        title.setMaxLength(200)
        layout.addWidget(title)
        content = QTextEdit()
        content.setAcceptRichText(False)
        content.setPlainText(entry.content)
        content.setObjectName("journalInput")
        content.setAccessibleName("Edit journal content")
        content.setMinimumHeight(180)
        layout.addWidget(content)
        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton("Cancel")
        cancel.setObjectName("journalSecondary")
        cancel.clicked.connect(self._cancel_edit)
        buttons.addWidget(cancel)
        save = QPushButton("Save Changes")
        save.setObjectName("journalPrimary")
        save.clicked.connect(
            lambda: self._save_edit(entry.id, title.text(), content.toPlainText())
        )
        buttons.addWidget(save)
        layout.addLayout(buttons)
        title.setFocus()
        return card

    def _begin_edit(self, entry: JournalItem) -> None:
        self._editing_id = entry.id
        self._render(self._entries)

    def _cancel_edit(self) -> None:
        self._editing_id = None
        self._render(self._entries)

    def add_entry(self) -> None:
        title, content = self.title_input.text(), self.content_input.toPlainText()
        self._run(
            lambda: self.service.add_entry(self.profile_id, title, content),
            lambda _: self._after_add(),
        )

    def _after_add(self) -> None:
        self.title_input.clear()
        self.content_input.clear()
        self._success("Journal entry saved successfully!")

    def _save_edit(self, entry_id: int, title: str, content: str) -> None:
        self._run(
            lambda: self.service.edit_entry(self.profile_id, entry_id, title, content),
            lambda _: self._after_edit(),
        )

    def _after_edit(self) -> None:
        self._editing_id = None
        self._success("Journal entry updated.")

    def _success(self, message: str) -> None:
        self.status.setText(message)
        self.status.setStyleSheet("color: #10b981;")
        self.refresh()

    def _confirm_delete(self, entry: JournalItem) -> None:
        dialog = QDialog(self)
        dialog.setObjectName("journalDeleteDialog")
        dialog.setWindowTitle("Delete journal entry")
        dialog.setStyleSheet("""
            QDialog#journalDeleteDialog { background: #1a1533; color: #f3f4f6; }
            QLabel { color: #f3f4f6; }
            QPushButton { background: #292143; color: #f3f4f6; padding: 10px 16px;
                border: 1px solid #483a64; border-radius: 9px; }
            QPushButton#journalConfirmDelete { background: #be3153; border-color: #e44970; }
        """)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(24, 24, 24, 24)
        message = _label(f"Delete '{entry.title}'?", "journalHeading")
        layout.addWidget(message)
        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton("Cancel")
        cancel.setDefault(True)
        cancel.clicked.connect(dialog.reject)
        buttons.addWidget(cancel)
        confirm = QPushButton("Delete entry")
        confirm.setObjectName("journalConfirmDelete")
        confirm.clicked.connect(dialog.accept)
        buttons.addWidget(confirm)
        layout.addLayout(buttons)
        cancel.setFocus()
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        dialog.deleteLater()
        if accepted:
            self._run(
                lambda: self.service.delete_entry(self.profile_id, entry.id),
                lambda _: self._success("Journal entry deleted."),
            )

    def shutdown(self) -> None:
        self._worker.shutdown()
