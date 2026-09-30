"""Profile-scoped journal operations for the desktop timeline."""

from sqlalchemy import select

from solar_forge_desktop.storage import JournalEntry, JournalItem, Profile, Storage, utc_now


class JournalService:
    def __init__(self, storage: Storage):
        self.storage = storage

    @staticmethod
    def _validate(title: str, content: str) -> tuple[str, str]:
        title = title.strip()
        content = content.strip()
        if not title:
            raise ValueError("Journal title is required.")
        if len(title) > 200:
            raise ValueError("Journal title must be 200 characters or fewer.")
        if not content:
            raise ValueError("Journal entry content is required.")
        return title, content

    def list_entries(self, profile_id: int, limit: int = 200) -> tuple[JournalItem, ...]:
        if not 1 <= limit <= 500:
            raise ValueError("Journal history limit must be between 1 and 500.")
        with self.storage.sessions() as session:
            if session.get(Profile, profile_id) is None:
                raise ValueError("Profile not found.")
            rows = session.scalars(
                select(JournalEntry)
                .where(JournalEntry.profile_id == profile_id)
                .order_by(JournalEntry.created_at.desc(), JournalEntry.id.desc())
                .limit(limit)
            ).all()
            return tuple(
                JournalItem(row.id, row.title, row.content, row.created_at, row.updated_at)
                for row in rows
            )

    def add_entry(self, profile_id: int, title: str, content: str) -> int:
        title, content = self._validate(title, content)
        with self.storage.sessions.begin() as session:
            if session.get(Profile, profile_id) is None:
                raise ValueError("Profile not found.")
            now = utc_now()
            entry = JournalEntry(
                profile_id=profile_id, title=title, content=content,
                created_at=now, updated_at=now,
            )
            session.add(entry)
            session.flush()
            return entry.id

    def edit_entry(self, profile_id: int, entry_id: int, title: str, content: str) -> None:
        title, content = self._validate(title, content)
        with self.storage.sessions.begin() as session:
            entry = session.scalar(
                select(JournalEntry).where(
                    JournalEntry.id == entry_id, JournalEntry.profile_id == profile_id
                )
            )
            if entry is None:
                raise ValueError("Journal entry not found.")
            entry.title = title
            entry.content = content
            entry.updated_at = utc_now()

    def delete_entry(self, profile_id: int, entry_id: int) -> None:
        with self.storage.sessions.begin() as session:
            entry = session.scalar(
                select(JournalEntry).where(
                    JournalEntry.id == entry_id, JournalEntry.profile_id == profile_id
                )
            )
            if entry is None:
                raise ValueError("Journal entry not found.")
            session.delete(entry)
