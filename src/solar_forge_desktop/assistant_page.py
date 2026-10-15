"""Opt-in local questions and explicitly approved record changes."""

from dataclasses import replace

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from solar_forge_desktop.assistant import AssistantReply, AssistantService
from solar_forge_desktop.assistant_actions import AssistantActionService, Proposal
from solar_forge_desktop.assistant_settings import (
    AssistantSettings,
    AssistantSettingsStore,
    validate_settings,
)
from solar_forge_desktop.local_models import LocalModelClient
from solar_forge_desktop.storage import Storage
from solar_forge_desktop.workers import BackgroundWorker

STYLE = """
QWidget#assistantPage { background: #0a0712; color: #f3f4f6; }
QLabel#assistantTitle { color: #f3f4f6; font-size: 28px; font-weight: 700; }
QLabel#assistantHint { color: #a1a1aa; }
QLabel#assistantStatus { color: #d6b4ff; }
QComboBox, QPlainTextEdit { background: #211b39; color: #f3f4f6;
    border: 1px solid #39314e; border-radius: 10px; padding: 9px; }
QComboBox QAbstractItemView { background: #211b39; color: #f3f4f6; }
QPlainTextEdit:focus { border-color: #8b5cf6; }
"""


class AssistantPage(QWidget):
    action_applied = Signal(str)

    def __init__(self, storage: Storage, settings: AssistantSettingsStore,
                 profile_id: int, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.profile_id = profile_id
        self.service = AssistantService(storage, settings, profile_id)
        self.actions = AssistantActionService(storage, settings, profile_id)
        self.pending: Proposal | None = None
        self._worker = BackgroundWorker(self, "solar-forge-assistant")
        self._worker.busy_changed.connect(self._set_busy)
        self._worker.failed.connect(self._show_error)
        self.setStyleSheet(STYLE)
        self._build()
        self._load()

    def _build(self) -> None:
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        page = QWidget()
        page.setObjectName("assistantPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(48, 36, 48, 36)
        layout.setSpacing(12)
        title = QLabel("Local assistant")
        title.setObjectName("assistantTitle")
        layout.addWidget(title)
        note = QLabel(
            "Off until you enable it. Questions and the selected record summaries go "
            "only to a model server on this computer. Proposed changes require your approval."
        )
        note.setObjectName("assistantHint")
        note.setWordWrap(True)
        layout.addWidget(note)

        layout.addWidget(QLabel("Model server"))
        self.provider = QComboBox()
        self.provider.setAccessibleName("Local model server")
        self.provider.addItem("Ollama", "ollama")
        self.provider.addItem("llama.cpp", "llama.cpp")
        self.provider.currentIndexChanged.connect(self._default_endpoint)
        layout.addWidget(self.provider)
        self.endpoint = QLineEdit()
        self.endpoint.setAccessibleName("Local model address")
        self.endpoint.setPlaceholderText("http://127.0.0.1:11434")
        layout.addWidget(self.endpoint)
        self.model = QComboBox()
        self.model.setEditable(True)
        self.model.setAccessibleName("Local model")
        self.model.lineEdit().setPlaceholderText("Test connection, then choose a model")
        layout.addWidget(self.model)
        self.test_button = QPushButton("Test connection and list models")
        self.test_button.clicked.connect(self._test_connection)
        layout.addWidget(self.test_button)

        scope = QLabel("Records this member allows the assistant to read")
        scope.setWordWrap(True)
        layout.addWidget(scope)
        self.tasks = QCheckBox("Visible open tasks")
        self.tasks.setAccessibleName("Allow assistant to read visible tasks")
        layout.addWidget(self.tasks)
        self.calendar = QCheckBox("Visible calendar events in the next 14 days")
        self.calendar.setAccessibleName("Allow assistant to read visible calendar events")
        layout.addWidget(self.calendar)
        actions = QHBoxLayout()
        self.enable_button = QPushButton("Save and enable")
        self.enable_button.setObjectName("primary")
        self.enable_button.clicked.connect(self._enable)
        actions.addWidget(self.enable_button)
        self.disable_button = QPushButton("Disable assistant")
        self.disable_button.clicked.connect(self._disable)
        actions.addWidget(self.disable_button)
        actions.addStretch()
        layout.addLayout(actions)
        self.status = QLabel()
        self.status.setObjectName("assistantStatus")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        layout.addSpacing(14)
        layout.addWidget(QLabel("Ask about your selected records"))
        self.question = QLineEdit()
        self.question.setAccessibleName("Question for local assistant")
        self.question.setMaxLength(500)
        self.question.setPlaceholderText("What is due this week?")
        self.question.returnPressed.connect(self._ask)
        layout.addWidget(self.question)
        self.ask_button = QPushButton("Ask local assistant")
        self.ask_button.clicked.connect(self._ask)
        layout.addWidget(self.ask_button)
        self.answer = QPlainTextEdit()
        self.answer.setObjectName("assistantAnswer")
        self.answer.setAccessibleName("Assistant answer")
        self.answer.setReadOnly(True)
        self.answer.setPlaceholderText("The answer will appear here.")
        self.answer.setMinimumHeight(115)
        layout.addWidget(self.answer)
        accuracy_note = QLabel("Model answers may be wrong. Check the records below.")
        accuracy_note.setObjectName("assistantHint")
        layout.addWidget(accuracy_note)
        sources_label = QLabel("Record summaries sent with the question")
        sources_label.setObjectName("assistantHint")
        layout.addWidget(sources_label)
        self.records = QPlainTextEdit()
        self.records.setObjectName("assistantRecords")
        self.records.setAccessibleName("Records used by the assistant")
        self.records.setReadOnly(True)
        self.records.setPlaceholderText("No records sent yet.")
        self.records.setMinimumHeight(115)
        layout.addWidget(self.records)

        layout.addSpacing(14)
        action_title = QLabel("Request one change")
        layout.addWidget(action_title)
        action_hint = QLabel(
            "Create a task, update one of your open tasks, or create a calendar event. "
            "The model drafts one change; nothing is saved until you review and approve it."
        )
        action_hint.setObjectName("assistantHint")
        action_hint.setWordWrap(True)
        layout.addWidget(action_hint)
        self.change_request = QLineEdit()
        self.change_request.setAccessibleName("Change request for local assistant")
        self.change_request.setMaxLength(500)
        self.change_request.setPlaceholderText("Add a private task to call the dentist tomorrow")
        layout.addWidget(self.change_request)
        self.propose_button = QPushButton("Draft change for review")
        self.propose_button.clicked.connect(self._propose)
        layout.addWidget(self.propose_button)
        self.preview = QPlainTextEdit()
        self.preview.setAccessibleName("Exact proposed change")
        self.preview.setReadOnly(True)
        self.preview.setPlaceholderText("A proposed change will appear here.")
        self.preview.setMinimumHeight(155)
        layout.addWidget(self.preview)
        decision = QHBoxLayout()
        self.approve_button = QPushButton("Approve this change")
        self.approve_button.setObjectName("primary")
        self.approve_button.clicked.connect(self._approve)
        decision.addWidget(self.approve_button)
        self.cancel_button = QPushButton("Cancel proposal")
        self.cancel_button.clicked.connect(self._cancel)
        decision.addWidget(self.cancel_button)
        decision.addStretch()
        layout.addLayout(decision)
        layout.addWidget(QLabel("Recent assistant decisions"))
        self.history = QPlainTextEdit()
        self.history.setAccessibleName("Assistant action history")
        self.history.setReadOnly(True)
        self.history.setMinimumHeight(90)
        layout.addWidget(self.history)
        layout.addStretch()
        scroll.setWidget(page)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _load(self) -> None:
        try:
            settings = self.settings.load(self.profile_id)
        except ValueError as exc:
            settings = AssistantSettings()
            self.status.setText(str(exc))
        else:
            self.status.setText("Enabled for this member." if settings.enabled else
                                "Off for this member.")
        self.provider.setCurrentIndex(self.provider.findData(settings.provider))
        self.endpoint.setText(settings.endpoint)
        self.model.setCurrentText(settings.model)
        self.tasks.setChecked(settings.include_tasks)
        self.calendar.setChecked(settings.include_calendar)
        self.disable_button.setEnabled(settings.enabled)
        self.ask_button.setEnabled(settings.enabled)
        self.propose_button.setEnabled(settings.enabled)
        self._clear_proposal()
        self._refresh_history()

    def _default_endpoint(self) -> None:
        current = self.endpoint.text().strip()
        if current in ("", "http://127.0.0.1:11434", "http://127.0.0.1:8080"):
            port = 11434 if self.provider.currentData() == "ollama" else 8080
            self.endpoint.setText(f"http://127.0.0.1:{port}")

    def _form_settings(self, enabled: bool) -> AssistantSettings:
        return validate_settings(AssistantSettings(
            enabled, self.provider.currentData(), self.endpoint.text(),
            self.model.currentText(), self.tasks.isChecked(), self.calendar.isChecked(),
        ))

    def _test_connection(self) -> None:
        try:
            settings = self._form_settings(False)
        except ValueError as exc:
            self._show_error(exc)
            return
        self.status.setText("Checking the local model server…")
        self._worker.submit(lambda: LocalModelClient(settings).models(), self._models_found)

    def _models_found(self, result: object) -> None:
        models = tuple(result)
        current = self.model.currentText()
        self.model.clear()
        self.model.addItems(models)
        self.model.setCurrentText(current or (models[0] if models else ""))
        self.status.setText(
            f"Connected. {len(models)} local model(s) available." if models else
            "Connected, but no local models are installed."
        )

    def _enable(self) -> None:
        try:
            self.settings.save(self.profile_id, self._form_settings(True))
        except (OSError, ValueError) as exc:
            self._show_error(exc)
            return
        self.status.setText("Enabled for this member. Only checked categories are included.")
        self.disable_button.setEnabled(True)
        self.ask_button.setEnabled(True)
        self.propose_button.setEnabled(True)

    def _disable(self) -> None:
        try:
            if self.pending:
                self.actions.reject(self.pending)
            current = self.settings.load(self.profile_id)
            self.settings.save(self.profile_id, replace(current, enabled=False))
        except (OSError, ValueError) as exc:
            self._show_error(exc)
            return
        self.answer.clear()
        self.records.clear()
        self._clear_proposal()
        self._refresh_history()
        self.status.setText("Off for this member. No records will be sent.")
        self.disable_button.setEnabled(False)
        self.ask_button.setEnabled(False)
        self.propose_button.setEnabled(False)

    def _ask(self) -> None:
        try:
            saved = self.settings.load(self.profile_id)
            if not saved.enabled:
                raise ValueError("Enable the local assistant for this member first.")
            if self._form_settings(True) != saved:
                raise ValueError("Save your permission and model changes before asking.")
        except ValueError as exc:
            self._show_error(exc)
            return
        question = self.question.text()
        self.answer.clear()
        self.records.clear()
        self.status.setText("Reading selected records and asking the local model…")
        self._worker.submit(lambda: self.service.ask(question), self._answered)

    def _answered(self, result: object) -> None:
        if not self.settings.load(self.profile_id).enabled:
            return
        reply: AssistantReply = result
        self.answer.setPlainText(reply.answer)
        self.records.setPlainText("\n".join(reply.records))
        self.status.setText(f"Answer ready. {len(reply.records)} record summaries used.")

    def _propose(self) -> None:
        try:
            saved = self.settings.load(self.profile_id)
            if not saved.enabled or self._form_settings(True) != saved:
                raise ValueError("Enable the assistant and save permission changes first.")
            if self.pending:
                self.actions.reject(self.pending)
                self._clear_proposal()
                self._refresh_history()
        except (OSError, ValueError) as exc:
            self._show_error(exc)
            return
        request = self.change_request.text()
        self.status.setText("Drafting one change for your review…")
        self._worker.submit(lambda: self.actions.propose(request), self._proposed)

    def _proposed(self, result: object) -> None:
        if not self.settings.load(self.profile_id).enabled:
            return
        proposal: Proposal = result
        self.pending = proposal
        self.preview.setPlainText(proposal.preview(self.profile_id))
        self.records.setPlainText("\n".join(proposal.records))
        self.approve_button.setEnabled(True)
        self.cancel_button.setEnabled(True)
        self.status.setText("Review every field, then approve or cancel this one change.")

    def _approve(self) -> None:
        if self.pending is None:
            return
        proposal = self.pending
        self._clear_proposal()
        self.status.setText("Applying your approved change…")
        self._worker.submit(lambda: self.actions.approve(proposal),
                            lambda result: self._applied(proposal, result))

    def _applied(self, proposal: Proposal, result: object) -> None:
        self.status.setText(f"Approved change saved as #{result}.")
        self._refresh_history()
        self.action_applied.emit(proposal.operation)

    def _cancel(self) -> None:
        if self.pending is None:
            return
        try:
            self.actions.reject(self.pending)
        except (OSError, ValueError) as exc:
            self._show_error(exc)
            return
        self._clear_proposal()
        self._refresh_history()
        self.status.setText("Proposal canceled. No record was changed.")

    def _clear_proposal(self) -> None:
        self.pending = None
        self.preview.clear()
        self.approve_button.setEnabled(False)
        self.cancel_button.setEnabled(False)

    def _refresh_history(self) -> None:
        try:
            entries = self.actions.audit.recent()
            self.history.setPlainText("\n".join(
                f"{entry['at']} · {entry['decision']} · {entry['operation']} · "
                f"{entry['fields'].get('title', '')}" for entry in entries
            ))
        except (OSError, ValueError):
            self.history.setPlainText("Action history could not be read.")

    def _show_error(self, error: Exception) -> None:
        self.status.setText(str(error))

    def _set_busy(self, busy: bool) -> None:
        for control in (self.test_button, self.enable_button, self.ask_button,
                        self.propose_button):
            control.setEnabled(not busy)
        if busy:
            self.approve_button.setEnabled(False)
            self.cancel_button.setEnabled(False)
        if busy:
            self.disable_button.setEnabled(self.settings.load(self.profile_id).enabled)
        if not busy:
            try:
                enabled = self.settings.load(self.profile_id).enabled
            except ValueError:
                enabled = False
            self.disable_button.setEnabled(enabled)
            self.ask_button.setEnabled(enabled)
            self.propose_button.setEnabled(enabled)
            self.approve_button.setEnabled(enabled and self.pending is not None)
            self.cancel_button.setEnabled(enabled and self.pending is not None)

    def shutdown(self) -> None:
        self._worker.shutdown()
