"""Native Pet Care page with per-animal care and matching medicine history."""

from datetime import date
from typing import Callable

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QBoxLayout,
    QCheckBox,
    QComboBox,
    QDateEdit,
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

from solar_forge_desktop.calendar_widgets import CALENDAR_STYLE, SELECTOR_STYLE, style_calendar
from solar_forge_desktop.pets import CARE_CATEGORIES, CareItem, PetItem, PetService, PetView
from solar_forge_desktop.workers import BackgroundWorker

CATEGORY_NAMES = {
    "feeding": "Feeding", "grooming": "Grooming", "flea": "Flea treatment",
    "vet": "Vet appointment", "weight": "Weight", "note": "Note",
}
STYLE = """
QWidget#petPage, QWidget#petBody { background: #0a0712; }
QScrollArea#petScroll, QScrollArea#petSwitcherScroll { background: #0a0712; border: none; }
QFrame#petCard { background: #1a1533; border: 1px solid #302943;
    border-radius: 16px; }
QLabel#petEyebrow { color: #ec4899; font-size: 11px; font-weight: 700; }
QLabel#petTitle { color: #f3f4f6; font-size: 32px; font-weight: 700; }
QLabel#petHeading { color: #f3f4f6; font-size: 19px; font-weight: 700; }
QLabel#petText { color: #f3f4f6; font-size: 14px; }
QLabel#petMuted { color: #a1a1aa; }
QLabel#petStatus { color: #fb7185; }
QLineEdit#petInput, QTextEdit#petNotes, QDateEdit#petDate, QComboBox#petCategory {
    background: #211b30; color: #f3f4f6; border: 1px solid #302943;
    border-radius: 9px; padding: 9px 11px; }
QLineEdit#petInput:focus, QTextEdit#petNotes:focus,
QDateEdit#petDate:focus, QComboBox#petCategory:focus { border-color: #8b5cf6; }
QComboBox#petCategory QAbstractItemView { background: #211b30; color: #f3f4f6; }
QPushButton#petPrimary { background: #8b5cf6; color: white; border: none;
    border-radius: 9px; padding: 10px 14px; font-weight: 700; }
QPushButton#petSecondary, QPushButton#petTab { background: #292143;
    color: #f3f4f6; border: 1px solid #483a64; border-radius: 10px;
    padding: 8px 13px; }
QPushButton#petTab:checked { background: #302348; border-color: #8b5cf6; }
QLabel#petAvatar { background: #8b5cf6; color: white; border-radius: 15px;
    font-weight: 700; }
QPushButton#petDanger { background: #3a1d39; color: #fb7185;
    border: 1px solid #5b3048; border-radius: 9px; padding: 8px 12px; }
QCheckBox#petCheckbox { color: #a1a1aa; spacing: 9px; }
QCheckBox#petCheckbox::indicator { width: 18px; height: 18px;
    border-radius: 5px; border: 1px solid #6f588e; background: #211b30; }
QCheckBox#petCheckbox::indicator:checked { background: #8b5cf6;
    border-color: #8b5cf6; }
QScrollBar:vertical { background: #151027; width: 10px; }
QScrollBar::handle:vertical { background: #483a64; border-radius: 5px; min-height: 28px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
""" + CALENDAR_STYLE + SELECTOR_STYLE


def _label(text: str, name: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName(name)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    return label


def _card() -> tuple[QFrame, QVBoxLayout]:
    card = QFrame()
    card.setObjectName("petCard")
    box = QVBoxLayout(card)
    box.setContentsMargins(22, 20, 22, 20)
    box.setSpacing(10)
    return card, box


def _field(name: str, placeholder: str = "") -> QLineEdit:
    field = QLineEdit()
    field.setObjectName("petInput")
    field.setAccessibleName(name)
    field.setPlaceholderText(placeholder)
    return field


def _clear(layout: QVBoxLayout | QHBoxLayout) -> None:
    while layout.count():
        part = layout.takeAt(0)
        if widget := part.widget():
            widget.deleteLater()
        elif nested := part.layout():
            _clear(nested)


class PetPage(QWidget):
    def __init__(self, service: PetService, profile_id: int,
                 open_medicine: Callable[[], None]):
        super().__init__()
        self.service = service
        self.profile_id = profile_id
        self.open_medicine = open_medicine
        self.selected_id: int | None = None
        self._serial = 0
        self.setObjectName("petPage")
        self.setStyleSheet(STYLE)
        self._build()
        self._worker = BackgroundWorker(self, "solar-forge-pets")
        self._worker.busy_changed.connect(self._set_busy)
        self._worker.failed.connect(self._show_error)

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setObjectName("petScroll")
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        body = QWidget()
        body.setObjectName("petBody")
        scroll.setWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(48, 36, 48, 40)
        layout.setSpacing(17)
        layout.addWidget(_label("YOUR ANIMALS", "petEyebrow"))
        layout.addWidget(_label("Pet Care", "petTitle"))
        layout.addWidget(_label("One clear care record for each pet.", "petMuted"))
        self.status = _label("", "petStatus")
        self.status.setAccessibleName("Pet status")
        layout.addWidget(self.status)
        self.status.hide()
        switcher = QHBoxLayout()
        switcher_scroll = QScrollArea()
        switcher_scroll.setObjectName("petSwitcherScroll")
        switcher_scroll.setWidgetResizable(True)
        switcher_scroll.setFixedHeight(76)
        switcher_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        switcher_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        switcher_widget = QWidget()
        self.tabs = QHBoxLayout(switcher_widget)
        self.tabs.setContentsMargins(0, 0, 0, 0)
        self.tabs.setSpacing(9)
        switcher_scroll.setWidget(switcher_widget)
        switcher.addWidget(switcher_scroll, 1)
        self.add_pet_toggle = QPushButton("+")
        self.add_pet_toggle.setObjectName("petPrimary")
        self.add_pet_toggle.setAccessibleName("Add pet")
        self.add_pet_toggle.setFixedSize(44, 44)
        self.add_pet_toggle.clicked.connect(
            lambda: self.pet_form_card.setVisible(not self.pet_form_card.isVisible())
        )
        switcher.addWidget(self.add_pet_toggle)
        layout.addLayout(switcher)
        self._build_pet_form(layout)
        self.welcome_card, welcome_box = _card()
        title = _label("Add Your First Animal", "petHeading")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_box.addWidget(title)
        hint = _label(
            "Use the + above to create a profile. Every care update will stay "
            "on that animal's own screen.",
            "petMuted",
        )
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_box.addWidget(hint)
        layout.addWidget(self.welcome_card)
        self._build_profile(layout)
        self.columns = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.columns.setSpacing(24)
        self._build_care_form()
        self._build_history()
        layout.addLayout(self.columns)
        layout.addStretch()
        self.profile_card.hide()
        self.care_card.hide()
        self.history_widget.hide()
        self._apply_responsive()

    def _build_pet_form(self, layout: QVBoxLayout) -> None:
        self.pet_form_card, form = _card()
        form.addWidget(_label("Add Pet", "petHeading"))
        self.pet_name = _field("Pet name")
        self.pet_name.setMaxLength(100)
        self.pet_type = _field("Animal type", "Dog, cat, rabbit…")
        self.pet_type.setMaxLength(60)
        self.pet_breed = _field("Breed", "Optional")
        self.pet_breed.setMaxLength(100)
        for label, field in (("NAME", self.pet_name), ("ANIMAL", self.pet_type),
                             ("BREED — OPTIONAL", self.pet_breed)):
            form.addWidget(_label(label, "petMuted"))
            form.addWidget(field)
        self.has_birth_date = QCheckBox("Birth date — optional")
        self.has_birth_date.setObjectName("petCheckbox")
        form.addWidget(self.has_birth_date)
        self.pet_birth_date = QDateEdit()
        self.pet_birth_date.setObjectName("petDate")
        self.pet_birth_date.setAccessibleName("Pet birth date")
        self.pet_birth_date.setDisplayFormat("MMM d, yyyy")
        self.pet_birth_date.setDate(QDate.currentDate())
        self.pet_birth_date.setMaximumDate(QDate.currentDate())
        self.pet_birth_date.setCalendarPopup(True)
        style_calendar(self.pet_birth_date.calendarWidget())
        self.has_birth_date.toggled.connect(self.pet_birth_date.setVisible)
        form.addWidget(self.pet_birth_date)
        self.pet_birth_date.hide()
        form.addWidget(_label("PROFILE NOTES — OPTIONAL", "petMuted"))
        self.pet_notes = QTextEdit()
        self.pet_notes.setObjectName("petNotes")
        self.pet_notes.setAccessibleName("Pet profile notes")
        self.pet_notes.setPlaceholderText("Allergies, temperament, microchip…")
        self.pet_notes.setFixedHeight(75)
        form.addWidget(self.pet_notes)
        self.save_pet_button = QPushButton("Save pet")
        self.save_pet_button.setObjectName("petPrimary")
        self.save_pet_button.clicked.connect(self.add_pet)
        form.addWidget(self.save_pet_button)
        layout.addWidget(self.pet_form_card)
        self.pet_form_card.hide()

    def _build_profile(self, layout: QVBoxLayout) -> None:
        self.profile_card, box = _card()
        box.addWidget(_label("SELECTED PET", "petEyebrow"))
        profile_row = QHBoxLayout()
        description = QVBoxLayout()
        self.profile_name = _label("", "petHeading")
        description.addWidget(self.profile_name)
        self.profile_meta = _label("", "petMuted")
        description.addWidget(self.profile_meta)
        self.profile_notes = _label("", "petText")
        description.addWidget(self.profile_notes)
        profile_row.addLayout(description, 1)
        self.remove_pet_button = QPushButton("Remove pet")
        self.remove_pet_button.setObjectName("petDanger")
        self.remove_pet_button.clicked.connect(self._confirm_delete_pet)
        profile_row.addWidget(self.remove_pet_button, 0, Qt.AlignmentFlag.AlignTop)
        box.addLayout(profile_row)
        layout.addWidget(self.profile_card)

    def _build_care_form(self) -> None:
        self.care_card, box = _card()
        box.addWidget(_label("Add Care Update", "petHeading"))
        self.care_hint = _label("", "petMuted")
        box.addWidget(self.care_hint)
        box.addWidget(_label("CARE TYPE", "petMuted"))
        self.care_category = QComboBox()
        self.care_category.setObjectName("petCategory")
        self.care_category.setAccessibleName("Care type")
        for value in CARE_CATEGORIES:
            self.care_category.addItem(CATEGORY_NAMES[value], value)
        self.care_category.currentIndexChanged.connect(self._toggle_care_weight)
        box.addWidget(self.care_category)
        box.addWidget(_label("DATE", "petMuted"))
        self.care_date = QDateEdit()
        self.care_date.setObjectName("petDate")
        self.care_date.setAccessibleName("Care date")
        self.care_date.setDisplayFormat("MMM d, yyyy")
        self.care_date.setDate(QDate.currentDate())
        self.care_date.setCalendarPopup(True)
        style_calendar(self.care_date.calendarWidget())
        box.addWidget(self.care_date)
        self.weight_group = QWidget()
        weight_box = QVBoxLayout(self.weight_group)
        weight_box.setContentsMargins(0, 0, 0, 0)
        weight_box.addWidget(_label("WEIGHT (LB)", "petMuted"))
        self.care_weight = _field("Pet weight in pounds")
        weight_box.addWidget(self.care_weight)
        box.addWidget(self.weight_group)
        self.weight_group.hide()
        box.addWidget(_label("DETAILS", "petMuted"))
        self.care_details = QTextEdit()
        self.care_details.setObjectName("petNotes")
        self.care_details.setAccessibleName("Care details")
        self.care_details.setPlaceholderText(
            "Food and amount, treatment, appointment time, or note…"
        )
        self.care_details.setFixedHeight(100)
        box.addWidget(self.care_details)
        self.add_record_button = QPushButton("Add update")
        self.add_record_button.setObjectName("petPrimary")
        self.add_record_button.clicked.connect(self.add_record)
        box.addWidget(self.add_record_button)
        self.columns.addWidget(self.care_card, 11, Qt.AlignmentFlag.AlignTop)

    def _build_history(self) -> None:
        self.history_widget = QWidget()
        history = QVBoxLayout(self.history_widget)
        history.setContentsMargins(0, 0, 0, 0)
        history.setSpacing(0)
        care_heading = QHBoxLayout()
        care_heading.addWidget(_label("Care History", "petHeading"))
        care_heading.addStretch()
        self.record_count = _label("0 updates", "petMuted")
        care_heading.addWidget(self.record_count)
        history.addLayout(care_heading)
        history.addSpacing(12)
        self.records_layout = QVBoxLayout()
        self.records_layout.setSpacing(12)
        history.addLayout(self.records_layout)
        history.addSpacing(28)
        medicine_heading = QHBoxLayout()
        medicine_heading.addWidget(_label("Medication History", "petHeading"))
        medicine_heading.addStretch()
        open_button = QPushButton("Open Medicine Tracker")
        open_button.setObjectName("petSecondary")
        open_button.clicked.connect(self.open_medicine)
        medicine_heading.addWidget(open_button)
        history.addLayout(medicine_heading)
        history.addSpacing(12)
        self.medicine_layout = QVBoxLayout()
        self.medicine_layout.setSpacing(12)
        history.addLayout(self.medicine_layout)
        history.addStretch()
        self.columns.addWidget(self.history_widget, 19)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_responsive()

    def _apply_responsive(self) -> None:
        self.columns.setDirection(
            QBoxLayout.Direction.TopToBottom if self.width() < 900
            else QBoxLayout.Direction.LeftToRight
        )

    def _run(self, action: Callable[[], object], done: Callable[[object], None]) -> None:
        self._worker.submit(action, done)

    def _set_busy(self, busy: bool) -> None:
        self.save_pet_button.setEnabled(not busy)
        self.add_record_button.setEnabled(not busy)
        self.remove_pet_button.setEnabled(not busy)

    def _show_error(self, error: Exception) -> None:
        self.status.setText(
            str(error) if isinstance(error, ValueError)
            else "The pet update could not be saved. Please try again."
        )
        self.status.setStyleSheet("color: #fb7185;")
        self.status.show()

    def activate(self) -> None:
        self.refresh()

    def refresh(self) -> None:
        self._serial += 1
        serial = self._serial
        selected = self.selected_id
        self._run(
            lambda: self.service.view(self.profile_id, selected),
            lambda result: self._render(result) if serial == self._serial else None,
        )

    def select_pet(self, pet_id: int) -> None:
        self.selected_id = pet_id
        self.refresh()

    def _render(self, view: PetView) -> None:
        self.selected_id = view.selected.id if view.selected else None
        _clear(self.tabs)
        for pet in view.pets:
            tab = QPushButton()
            tab.setObjectName("petTab")
            tab.setAccessibleName(f"Select {pet.name}")
            tab.setFixedWidth(160)
            tab.setFixedHeight(58)
            tab_box = QHBoxLayout(tab)
            tab_box.setContentsMargins(8, 5, 8, 5)
            avatar = _label(pet.name[:1].upper(), "petAvatar")
            avatar.setFixedSize(30, 30)
            avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
            tab_box.addWidget(avatar)
            tab_text = QVBoxLayout()
            tab_text.setSpacing(0)
            tab_text.addWidget(_label(pet.name, "petText"))
            tab_text.addWidget(_label(pet.animal_type, "petMuted"))
            tab_box.addLayout(tab_text, 1)
            tab.setCheckable(True)
            tab.setChecked(pet.id == self.selected_id)
            tab.clicked.connect(lambda _checked=False, pet_id=pet.id: self.select_pet(pet_id))
            self.tabs.addWidget(tab)
        self.tabs.addStretch()
        has_pet = view.selected is not None
        self.welcome_card.setVisible(not has_pet)
        self.profile_card.setVisible(has_pet)
        self.care_card.setVisible(has_pet)
        self.history_widget.setVisible(has_pet)
        if not has_pet:
            return
        selected = view.selected
        self.profile_name.setText(selected.name)
        meta = selected.animal_type
        if selected.breed:
            meta += f" · {selected.breed}"
        if selected.birth_date:
            meta += f" · Born {selected.birth_date:%b %Y}"
        self.profile_meta.setText(meta)
        self.profile_notes.setText(selected.notes or "")
        self.care_hint.setText(f"Everything added here belongs only to {selected.name}.")
        self.record_count.setText(f"{view.care_count} updates")
        _clear(self.records_layout)
        if not view.records:
            card, box = _card()
            box.addWidget(_label("No Care Updates Yet", "petText"))
            box.addWidget(_label(
                f"Add {selected.name}'s feeding, grooming, treatment, vet, weight, or notes.",
                "petMuted",
            ))
            self.records_layout.addWidget(card)
        for record in view.records:
            self.records_layout.addWidget(self._record_card(selected, record))
        _clear(self.medicine_layout)
        if not view.medicines:
            card, box = _card()
            box.addWidget(_label(
                f"No Medicine Tracker records match {selected.name}.", "petMuted"
            ))
            self.medicine_layout.addWidget(card)
        for medicine in view.medicines:
            card, box = _card()
            box.addWidget(_label(medicine.medicine_name, "petText"))
            given = date.fromisoformat(medicine.given_at[:10])
            box.addWidget(_label(
                f"{medicine.dosage} · Given {given:%b} {given.day:02d}, {given.year}",
                "petMuted",
            ))
            self.medicine_layout.addWidget(card)

    def _record_card(self, pet: PetItem, record: CareItem) -> QFrame:
        card, box = _card()
        box.setContentsMargins(24, 22, 24, 22)
        row = QHBoxLayout()
        row.setSpacing(18)
        icon = _label(CATEGORY_NAMES[record.category][0], "petEyebrow")
        icon.setFixedWidth(27)
        row.addWidget(icon)
        content = QVBoxLayout()
        content.setSpacing(8)
        heading = QHBoxLayout()
        heading.addWidget(_label(CATEGORY_NAMES[record.category], "petText"))
        heading.addStretch()
        heading.addWidget(_label(f"{record.record_date:%b %d, %Y}", "petMuted"))
        content.addLayout(heading)
        prefix = f"{record.weight:.1f} lb · " if record.weight is not None else ""
        content.addWidget(_label(prefix + record.details, "petMuted"))
        row.addLayout(content, 1)
        delete = QPushButton("×")
        delete.setObjectName("petDanger")
        delete.setAccessibleName(f"Remove {CATEGORY_NAMES[record.category]} care update")
        delete.clicked.connect(lambda: self._confirm_delete_record(pet, record))
        row.addWidget(delete, 0, Qt.AlignmentFlag.AlignTop)
        box.addLayout(row)
        return card

    def _toggle_care_weight(self) -> None:
        weighted = self.care_category.currentData() == "weight"
        self.weight_group.setVisible(weighted)
        if not weighted:
            self.care_weight.clear()

    @staticmethod
    def _selected_date(field: QDateEdit) -> date:
        value = field.date()
        return date(value.year(), value.month(), value.day())

    def add_pet(self) -> None:
        name = self.pet_name.text()
        animal = self.pet_type.text()
        breed = self.pet_breed.text()
        born = self._selected_date(self.pet_birth_date) if self.has_birth_date.isChecked() else None
        notes = self.pet_notes.toPlainText()
        self._run(
            lambda: self.service.add_pet(self.profile_id, name, animal, breed, born, notes),
            lambda pet_id: self._after_pet_added(pet_id, name.strip()),
        )

    def _after_pet_added(self, pet_id: int, name: str) -> None:
        self.selected_id = pet_id
        self.pet_form_card.hide()
        self.pet_name.clear()
        self.pet_type.clear()
        self.pet_breed.clear()
        self.has_birth_date.setChecked(False)
        self.pet_notes.clear()
        self.status.setText(f"Added {name}.")
        self.status.setStyleSheet("color: #10b981;")
        self.status.show()
        self.refresh()

    def add_record(self) -> None:
        selected = self.selected_id
        if selected is None:
            return
        category = self.care_category.currentData()
        day = self._selected_date(self.care_date)
        details = self.care_details.toPlainText()
        weight = self.care_weight.text()
        name = self.profile_name.text()
        self._run(
            lambda: self.service.add_record(
                self.profile_id, selected, category, day, details, weight
            ),
            lambda _: self._after_record_added(category, name),
        )

    def _after_record_added(self, category: str, name: str) -> None:
        self.care_details.clear()
        self.care_weight.clear()
        self.status.setText(f"Added {category} record for {name}.")
        self.status.setStyleSheet("color: #10b981;")
        self.status.show()
        self.refresh()

    def _confirm(self, title: str, message: str) -> bool:
        dialog = QDialog(self)
        dialog.setObjectName("petDeleteDialog")
        dialog.setWindowTitle(title)
        dialog.setStyleSheet(STYLE + "QDialog#petDeleteDialog { background: #1a1533; }")
        box = QVBoxLayout(dialog)
        box.setContentsMargins(24, 24, 24, 24)
        box.addWidget(_label(message, "petHeading"))
        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton("Cancel")
        cancel.setObjectName("petSecondary")
        cancel.setDefault(True)
        cancel.clicked.connect(dialog.reject)
        buttons.addWidget(cancel)
        remove = QPushButton("Remove")
        remove.setObjectName("petDanger")
        remove.clicked.connect(dialog.accept)
        buttons.addWidget(remove)
        box.addLayout(buttons)
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        dialog.deleteLater()
        return accepted

    def _confirm_delete_record(self, pet: PetItem, record: CareItem) -> None:
        if self._confirm("Remove care update", "Remove this care update?"):
            self._run(
                lambda: self.service.delete_record(self.profile_id, pet.id, record.id),
                lambda _: self._after_delete("Care record removed."),
            )

    def _confirm_delete_pet(self) -> None:
        pet_id = self.selected_id
        name = self.profile_name.text()
        if pet_id is not None and self._confirm(
            "Remove pet", f"Remove {name} and all care records?"
        ):
            self._run(
                lambda: self.service.delete_pet(self.profile_id, pet_id),
                lambda _: self._after_pet_deleted(name),
            )

    def _after_delete(self, message: str) -> None:
        self.status.setText(message)
        self.status.setStyleSheet("color: #10b981;")
        self.status.show()
        self.refresh()

    def _after_pet_deleted(self, name: str) -> None:
        self.selected_id = None
        self._after_delete(f"Removed {name}.")

    def shutdown(self) -> None:
        self._worker.shutdown()
