"""Profile-scoped pet profiles, care history, and matching medicine doses."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select

from solar_forge_desktop.storage import (
    MedicineItem,
    MedicineLog,
    Pet,
    PetCareRecord,
    Profile,
    Storage,
    utc_now,
)

CARE_CATEGORIES = ("feeding", "grooming", "flea", "vet", "weight", "note")


@dataclass(frozen=True)
class PetItem:
    id: int
    name: str
    animal_type: str
    breed: str | None
    birth_date: date | None
    notes: str | None


@dataclass(frozen=True)
class CareItem:
    id: int
    category: str
    record_date: date
    details: str
    weight: Decimal | None


@dataclass(frozen=True)
class PetView:
    pets: tuple[PetItem, ...]
    selected: PetItem | None
    care_count: int
    records: tuple[CareItem, ...]
    medicine_count: int
    medicines: tuple[MedicineItem, ...]


def _date(value: date, message: str) -> str:
    if not isinstance(value, date) or isinstance(value, datetime):
        raise ValueError(message)
    return value.isoformat()


def _required(value: str, field: str, maximum: int | None = None,
              *, required_message: str | None = None) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(required_message or f"{field} is required.")
    result = value.strip()
    if maximum is not None and len(result) > maximum:
        raise ValueError(f"{field} must be {maximum} characters or fewer.")
    return result


def _optional(value: str | None, maximum: int | None = None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Optional fields must be text.")
    result = value.strip() or None
    if result and maximum is not None and len(result) > maximum:
        raise ValueError(f"Must be {maximum} characters or fewer.")
    return result


def _pet_item(row: Pet) -> PetItem:
    return PetItem(
        row.id, row.name, row.animal_type, row.breed,
        date.fromisoformat(row.birth_date) if row.birth_date else None, row.notes,
    )


class PetService:
    def __init__(self, storage: Storage):
        self.storage = storage

    def view(self, profile_id: int, selected_id: int | None = None,
             limit: int = 200) -> PetView:
        if not 1 <= limit <= 500:
            raise ValueError("Pet history limit must be between 1 and 500.")
        with self.storage.sessions() as session:
            if session.get(Profile, profile_id) is None:
                raise ValueError("Profile not found.")
            rows = session.scalars(select(Pet).where(Pet.profile_id == profile_id)
                                   .order_by(Pet.name, Pet.id)).all()
            pets = tuple(_pet_item(row) for row in rows)
            selected = next((pet for pet in pets if pet.id == selected_id), None)
            if selected is None and pets:
                selected = pets[0]
            if selected is None:
                return PetView(pets, None, 0, (), 0, ())
            care_count = session.scalar(select(func.count()).select_from(PetCareRecord).where(
                PetCareRecord.pet_id == selected.id
            ))
            care_rows = session.scalars(select(PetCareRecord).where(
                PetCareRecord.pet_id == selected.id
            ).order_by(PetCareRecord.record_date.desc(),
                       PetCareRecord.created_at.desc(), PetCareRecord.id.desc())
                .limit(limit)).all()
            medicine_filter = (
                MedicineLog.profile_id == profile_id,
                MedicineLog.recipient == selected.name,
            )
            medicine_count = session.scalar(select(func.count()).select_from(MedicineLog)
                                            .where(*medicine_filter))
            medicines = session.scalars(select(MedicineLog).where(*medicine_filter)
                                        .order_by(MedicineLog.given_at.desc(),
                                                  MedicineLog.id.desc())
                                        .limit(limit)).all()
            return PetView(
                pets, selected, care_count,
                tuple(CareItem(row.id, row.category, date.fromisoformat(row.record_date),
                               row.details, Decimal(row.weight) if row.weight else None)
                      for row in care_rows),
                medicine_count,
                tuple(MedicineItem(row.id, row.recipient, row.medicine_name, row.dosage,
                                   row.given_at, row.next_due_at, row.created_at)
                      for row in medicines),
            )

    def add_pet(self, profile_id: int, name: str, animal_type: str,
                breed: str | None = None, birth_date: date | None = None,
                notes: str | None = None) -> int:
        if not isinstance(name, str) or not name.strip() or not isinstance(
            animal_type, str
        ) or not animal_type.strip():
            raise ValueError("Pet name and animal type are required.")
        name = _required(name, "Pet name", 100)
        animal_type = _required(animal_type, "Animal type", 60)
        breed = _optional(breed, 100)
        notes = _optional(notes)
        born = None
        if birth_date is not None:
            born = _date(birth_date, "Choose a valid birth date.")
        if birth_date is not None and birth_date > date.today():
            raise ValueError("Birth date cannot be in the future.")
        with self.storage.sessions.begin() as session:
            if session.get(Profile, profile_id) is None:
                raise ValueError("Profile not found.")
            pet = Pet(profile_id=profile_id, name=name, animal_type=animal_type,
                      breed=breed, birth_date=born, notes=notes, created_at=utc_now())
            session.add(pet)
            session.flush()
            return pet.id

    def add_record(self, profile_id: int, pet_id: int, category: str,
                   record_date: date, details: str, weight_raw: str | None = None) -> int:
        if not isinstance(category, str) or category.strip().lower() not in CARE_CATEGORIES:
            raise ValueError("Choose a valid care type.")
        category = category.strip().lower()
        details = _required(details, "Care details", required_message="Care details are required.")
        day = _date(record_date, "Choose a valid date.")
        weight = None
        if category == "weight":
            try:
                weight = Decimal(weight_raw.strip())
            except (AttributeError, InvalidOperation) as exc:
                raise ValueError("Enter a weight greater than zero.") from exc
            if not weight.is_finite() or weight <= 0:
                raise ValueError("Enter a weight greater than zero.")
        with self.storage.sessions.begin() as session:
            pet = session.scalar(select(Pet).where(Pet.id == pet_id,
                                                   Pet.profile_id == profile_id))
            if pet is None:
                raise ValueError("Pet not found.")
            record = PetCareRecord(pet_id=pet_id, category=category,
                                   record_date=day, details=details,
                                   weight=str(weight) if weight is not None else None,
                                   created_at=utc_now())
            session.add(record)
            session.flush()
            return record.id

    def delete_record(self, profile_id: int, pet_id: int, record_id: int) -> None:
        with self.storage.sessions.begin() as session:
            record = session.scalar(select(PetCareRecord).join(Pet).where(
                PetCareRecord.id == record_id, PetCareRecord.pet_id == pet_id,
                Pet.profile_id == profile_id
            ))
            if record is None:
                raise ValueError("Care record not found.")
            session.delete(record)

    def delete_pet(self, profile_id: int, pet_id: int) -> None:
        with self.storage.sessions.begin() as session:
            pet = session.scalar(select(Pet).where(Pet.id == pet_id,
                                                   Pet.profile_id == profile_id))
            if pet is None:
                raise ValueError("Pet not found.")
            session.delete(pet)
