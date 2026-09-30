"""Task application operations with explicit profile ownership."""

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
                         row.profile_id, row.visibility)
                for row in rows
            ]
            return (
                [item for item in items if not item.completed],
                [item for item in items if item.completed],
            )

    def add_task(self, profile_id: int, title: str, visibility: str = "private") -> int:
        clean_title = title.strip()
        if not clean_title:
            raise ValueError("Task title is required.")
        if len(clean_title) > 200:
            raise ValueError("Task title must be 200 characters or fewer.")
        visibility = require_visibility(visibility)
        with self.storage.sessions.begin() as session:
            require_actor(session, profile_id)
            task = Task(
                profile_id=profile_id, title=clean_title, completed=False,
                created_at=utc_now(), visibility=visibility,
            )
            session.add(task)
            session.flush()
            return task.id

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
