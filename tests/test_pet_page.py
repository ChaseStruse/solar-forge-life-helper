"""Native Pet Care interactions and navigation."""

from pathlib import Path

from PySide6.QtCore import QDate, Qt, QTimer
from PySide6.QtWidgets import QBoxLayout, QDialog, QPushButton

from solar_forge_desktop.medicine import MedicineService
from solar_forge_desktop.pets import PetService
from solar_forge_desktop.storage import Storage
from solar_forge_desktop.tasks import TaskService
from solar_forge_desktop.window import TaskWindow


def test_pet_page_add_switch_care_medicine_delete_and_restart(qtbot, tmp_path: Path) -> None:
    path = tmp_path / "solar-forge.db"
    storage = Storage(path)
    profile = storage.default_profile_id()
    MedicineService(storage).add_log(
        profile, "Luna", "Heartgard", "1 chew", "2026-09-27T08:00", "2026-10-27T08:00"
    )
    window = TaskWindow(TaskService(storage), profile, storage.close)
    qtbot.addWidget(window)
    window.show()
    card = next(item for item in window.app_cards
                if item.accessibleName() == "Open Pet Care")
    qtbot.mouseClick(card, Qt.MouseButton.LeftButton)
    page = window.pet_page
    assert window.pages.currentIndex() == 9
    assert window.pet_nav.isChecked()
    qtbot.waitUntil(lambda: page.welcome_card.isVisible())
    qtbot.waitUntil(page.save_pet_button.isEnabled)
    qtbot.mouseClick(page.add_pet_toggle, Qt.MouseButton.LeftButton)
    assert page.pet_form_card.isVisible()
    assert page.pet_birth_date.calendarWidget().objectName() == "solarForgeCalendar"
    page.pet_name.setText("Luna")
    page.pet_type.setText("Dog")
    page.pet_breed.setText("Lab")
    page.has_birth_date.setChecked(True)
    page.pet_birth_date.setDate(QDate(2020, 5, 1))
    page.pet_notes.setPlainText("Likes carrots")
    qtbot.mouseClick(page.save_pet_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: page.profile_name.text() == "Luna")
    assert not page.welcome_card.isVisible()
    assert "Born May 2020" in page.profile_meta.text()
    assert page.profile_notes.text() == "Likes carrots"
    medicine_labels = page.medicine_layout.itemAt(0).widget().findChildren(
        type(page.profile_name)
    )
    assert medicine_labels[0].text() == "Heartgard"
    window.resize(800, 600)
    qtbot.waitUntil(lambda: page.columns.direction() == QBoxLayout.Direction.TopToBottom)
    window.resize(1280, 800)
    page.care_category.setCurrentIndex(4)
    assert page.weight_group.isVisible()
    page.care_date.setDate(QDate(2026, 9, 28))
    assert page.care_date.calendarWidget().objectName() == "solarForgeCalendar"
    page.care_weight.setText("42.125")
    page.care_details.setPlainText("Home scale")
    qtbot.mouseClick(page.add_record_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: page.record_count.text() == "1 updates")
    record_labels = page.records_layout.itemAt(0).widget().findChildren(
        type(page.profile_name)
    )
    assert "42.1 lb" in record_labels[-1].text()
    luna = page.selected_id
    QTimer.singleShot(0, lambda: page.findChild(QDialog, "petDeleteDialog").reject())
    page._confirm_delete_pet()
    assert PetService(storage).view(profile, luna).care_count == 1
    QTimer.singleShot(0, lambda: page.findChild(QDialog, "petDeleteDialog").accept())
    page._confirm_delete_record(PetService(storage).view(profile, luna).selected,
                                PetService(storage).view(profile, luna).records[0])
    qtbot.waitUntil(lambda: page.record_count.text() == "0 updates")
    qtbot.mouseClick(page.add_pet_toggle, Qt.MouseButton.LeftButton)
    page.pet_name.setText("Milo")
    page.pet_type.setText("Cat")
    qtbot.mouseClick(page.save_pet_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: page.profile_name.text() == "Milo")
    page.select_pet(luna)
    qtbot.waitUntil(lambda: page.profile_name.text() == "Luna")
    QTimer.singleShot(0, lambda: page.findChild(QDialog, "petDeleteDialog").accept())
    page._confirm_delete_pet()
    qtbot.waitUntil(lambda: page.profile_name.text() == "Milo")
    assert PetService(storage).view(profile).selected.name == "Milo"
    window.close()
    reopened = Storage(path)
    assert PetService(reopened).view(profile).selected.name == "Milo"
    reopened.close()


def test_pet_search_validation_and_medicine_link(qtbot, tmp_path: Path) -> None:
    storage = Storage(tmp_path / "solar-forge.db")
    profile = storage.default_profile_id()
    window = TaskWindow(TaskService(storage), profile, storage.close)
    qtbot.addWidget(window)
    window.show()
    window.app_search.setText("animal")
    window.app_search.returnPressed.emit()
    page = window.pet_page
    assert window.pages.currentIndex() == 9
    qtbot.waitUntil(page.save_pet_button.isEnabled)
    qtbot.mouseClick(page.add_pet_toggle, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(page.save_pet_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: "required" in page.status.text())
    page.pet_name.setText("Luna")
    page.pet_type.setText("Dog")
    qtbot.mouseClick(page.save_pet_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: page.profile_name.text() == "Luna")
    page.care_details.setPlainText(" ")
    qtbot.mouseClick(page.add_record_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: "required" in page.status.text())
    page.care_category.setCurrentIndex(4)
    page.care_details.setPlainText("Scale")
    page.care_weight.setText("0")
    qtbot.mouseClick(page.add_record_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: "greater than zero" in page.status.text())
    medicine_button = next(button for button in page.findChildren(QPushButton)
                           if button.text() == "Open Medicine Tracker")
    qtbot.mouseClick(medicine_button, Qt.MouseButton.LeftButton)
    assert window.pages.currentIndex() == 4
    window.close()
