"""Profile-scoped medicine dose logging with local wall-clock schedules."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select

from solar_forge_desktop.storage import MedicineItem, MedicineLog, Profile, Storage, utc_now


@dataclass(frozen=True)
class MedicineView:
    total_count: int
    recipient_count: int
    logs: tuple[MedicineItem, ...]


class MedicineService:
    def __init__(self, storage: Storage):
        self.storage = storage

    @staticmethod
    def _time(value: str) -> datetime:
        try:
            parsed = datetime.strptime(value.strip(), "%Y-%m-%dT%H:%M")
        except ValueError as exc:
            raise ValueError("Given and next-dose times are required.") from exc
        if parsed.strftime("%Y-%m-%dT%H:%M") != value.strip():
            raise ValueError("Given and next-dose times are required.")
        return parsed

    def view(self, profile_id: int, limit: int = 200) -> MedicineView:
        if not 1 <= limit <= 500:
            raise ValueError("Medicine history limit must be between 1 and 500.")
        with self.storage.sessions() as session:
            if session.get(Profile, profile_id) is None:
                raise ValueError("Profile not found.")
            count = session.scalar(
                select(func.count()).select_from(MedicineLog).where(
                    MedicineLog.profile_id == profile_id
                )
            )
            recipients = session.scalar(
                select(func.count(func.distinct(func.lower(MedicineLog.recipient)))).where(
                    MedicineLog.profile_id == profile_id
                )
            )
            rows = session.scalars(
                select(MedicineLog)
                .where(MedicineLog.profile_id == profile_id)
                .order_by(MedicineLog.next_due_at, MedicineLog.given_at.desc(), MedicineLog.id)
                .limit(limit)
            ).all()
            return MedicineView(
                count,
                recipients,
                tuple(
                    MedicineItem(
                        row.id, row.recipient, row.medicine_name, row.dosage,
                        row.given_at, row.next_due_at, row.created_at,
                    )
                    for row in rows
                ),
            )

    def add_log(
        self, profile_id: int, recipient: str, medicine_name: str, dosage: str,
        given_at: str, next_due_at: str,
    ) -> int:
        recipient = recipient.strip()
        medicine_name = medicine_name.strip()
        dosage = dosage.strip()
        if not recipient:
            raise ValueError("Who the medicine is for is required.")
        if len(recipient) > 100:
            raise ValueError("Recipient must be 100 characters or fewer.")
        if not medicine_name:
            raise ValueError("Medicine name is required.")
        if len(medicine_name) > 150:
            raise ValueError("Medicine name must be 150 characters or fewer.")
        if not dosage:
            raise ValueError("Dosage is required.")
        if len(dosage) > 100:
            raise ValueError("Dosage must be 100 characters or fewer.")
        given = self._time(given_at)
        due = self._time(next_due_at)
        if due <= given:
            raise ValueError("The next dose must be scheduled after the given time.")
        with self.storage.sessions.begin() as session:
            if session.get(Profile, profile_id) is None:
                raise ValueError("Profile not found.")
            log = MedicineLog(
                profile_id=profile_id, recipient=recipient, medicine_name=medicine_name,
                dosage=dosage, given_at=given.isoformat(timespec="minutes"),
                next_due_at=due.isoformat(timespec="minutes"), created_at=utc_now(),
            )
            session.add(log)
            session.flush()
            return log.id

    def delete_log(self, profile_id: int, log_id: int) -> None:
        with self.storage.sessions.begin() as session:
            log = session.scalar(
                select(MedicineLog).where(
                    MedicineLog.id == log_id, MedicineLog.profile_id == profile_id
                )
            )
            if log is None:
                raise ValueError("Medicine log entry not found.")
            session.delete(log)
