"""Task application operations with explicit profile ownership."""

from datetime import datetime

from sqlalchemy import and_, or_, select

from solar_forge_desktop.household_access import (
    can_read,
    member_ids,
    require_actor,
    require_visibility,
)
from solar_forge_desktop.storage import Storage, Task, TaskItem, utc_now


class TaskService:
    def __init__(self, storage: Storage):
        self.storage = storage

    def list_tasks(self, profile_id: int) -> tuple[list[TaskItem], list[TaskItem]]:
        with self.storage.sessions() as session:
            household_profiles = member_ids(session, profile_id)
            rows = session.scalars(
                select(Task)
                .where(or_(
                    Task.profile_id == profile_id,
                    and_(Task.visibility == "household", Task.profile_id.in_(household_profiles)),
                ))
                .order_by(Task.completed, Task.created_at.desc(), Task.id.desc())
                .limit(500)
            ).all()
            items = [
                TaskItem(row.id, row.title, row.completed, row.created_at, row.completed_at,
                         row.profile_id, row.visibility, row.due_at)
                for row in rows
            ]
            return (
                [item for item in items if not item.completed],
                [item for item in items if item.completed],
            )

    def add_task(self, profile_id: int, title: str, visibility: str = "private",
                 due_at: datetime | None = None) -> int:
        clean_title = title.strip()
        if not clean_title:
            raise ValueError("Task title is required.")
        if len(clean_title) > 200:
            raise ValueError("Task title must be 200 characters or fewer.")
        visibility = require_visibility(visibility)
        due = self._due_value(due_at)
        with self.storage.sessions.begin() as session:
            require_actor(session, profile_id)
            task = Task(
                profile_id=profile_id, title=clean_title, completed=False,
                created_at=utc_now(), visibility=visibility, due_at=due,
            )
            session.add(task)
            session.flush()
            return task.id

    def get_task(self, profile_id: int, task_id: int) -> TaskItem:
        with self.storage.sessions() as session:
            require_actor(session, profile_id)
            row = session.get(Task, task_id)
            if row is None or not can_read(session, profile_id, row.profile_id, row.visibility):
                raise ValueError("Task not found.")
            return TaskItem(row.id, row.title, row.completed, row.created_at,
                            row.completed_at, row.profile_id, row.visibility, row.due_at)

    def find_owned_open_tasks(self, profile_id: int, terms: tuple[str, ...],
                              limit: int = 8) -> tuple[TaskItem, ...]:
        """Find bounded title matches for a member's assistant context."""
        if not terms:
            return ()
        with self.storage.sessions() as session:
            require_actor(session, profile_id)
            rows = session.scalars(select(Task).where(
                Task.profile_id == profile_id, Task.completed.is_(False)
            )).all()
            matches = [row for row in rows if any(term in row.title.casefold()
                                                   for term in terms)]
            matches.sort(key=lambda row: (-sum(term in row.title.casefold()
                                               for term in terms), -row.id))
            return tuple(TaskItem(row.id, row.title, row.completed, row.created_at,
                                  row.completed_at, row.profile_id, row.visibility, row.due_at)
                         for row in matches[:limit])

    def update_owned_task(self, profile_id: int, task_id: int, title: str,
                          due_at: datetime | None, expected: TaskItem) -> None:
        """Apply an approved replacement only if the owner's task is unchanged."""
        clean_title = title.strip() if isinstance(title, str) else ""
        if not clean_title or len(clean_title) > 200:
            raise ValueError("Task title is required and must be 200 characters or fewer.")
        due = self._due_value(due_at)
        with self.storage.sessions.begin() as session:
            require_actor(session, profile_id)
            row = session.get(Task, task_id)
            if row is None or row.profile_id != profile_id:
                raise ValueError("Only your own task can be updated by the assistant.")
            if (row.title, row.due_at, row.completed, row.visibility, row.created_at) != (
                    expected.title, expected.due_at, expected.completed,
                    expected.visibility, expected.created_at):
                raise ValueError("This task changed since the preview. Request a new proposal.")
            row.title = clean_title
            row.due_at = due

    @staticmethod
    def _due_value(due_at: datetime | None) -> str | None:
        if due_at is None:
            return None
        if not isinstance(due_at, datetime) or due_at.tzinfo is not None:
            raise ValueError("Task due date must be a local date and time.")
        return due_at.replace(second=0, microsecond=0).isoformat(timespec="minutes")

    def set_due_at(self, profile_id: int, task_id: int,
                   due_at: datetime | None) -> None:
        due = self._due_value(due_at)
        with self.storage.sessions.begin() as session:
            require_actor(session, profile_id)
            task = session.get(Task, task_id)
            if task is None or task.profile_id != profile_id:
                raise ValueError("Task not found.")
            task.due_at = due

    def toggle_task(self, profile_id: int, task_id: int) -> None:
        with self.storage.sessions.begin() as session:
            require_actor(session, profile_id)
            task = session.get(Task, task_id)
            if task is None or not can_read(session, profile_id, task.profile_id, task.visibility):
                raise ValueError("Task not found.")
            task.completed = not task.completed
            task.completed_at = utc_now() if task.completed else None

    def delete_task(self, profile_id: int, task_id: int) -> None:
        with self.storage.sessions.begin() as session:
            require_actor(session, profile_id)
            task = session.scalar(
                select(Task).where(Task.id == task_id, Task.profile_id == profile_id)
            )
            if task is None:
                raise ValueError("Task not found.")
            session.delete(task)

    def set_visibility(self, profile_id: int, task_id: int, visibility: str) -> None:
        visibility = require_visibility(visibility)
        with self.storage.sessions.begin() as session:
            require_actor(session, profile_id)
            task = session.scalar(select(Task).where(
                Task.id == task_id, Task.profile_id == profile_id
            ))
            if task is None:
                raise ValueError("Task not found.")
            task.visibility = visibility
