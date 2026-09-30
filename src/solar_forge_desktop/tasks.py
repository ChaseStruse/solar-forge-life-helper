"""Task application operations with explicit profile ownership."""

from sqlalchemy import select

from solar_forge_desktop.storage import Profile, Storage, Task, TaskItem, utc_now


class TaskService:
    def __init__(self, storage: Storage):
        self.storage = storage

    def _require_profile(self, session, profile_id: int) -> None:
        if session.get(Profile, profile_id) is None:
            raise ValueError("Profile not found.")

    def list_tasks(self, profile_id: int) -> tuple[list[TaskItem], list[TaskItem]]:
        with self.storage.sessions() as session:
            self._require_profile(session, profile_id)
            rows = session.scalars(
                select(Task)
                .where(Task.profile_id == profile_id)
                .order_by(Task.completed, Task.created_at.desc(), Task.id.desc())
                .limit(500)
            ).all()
            items = [
                TaskItem(row.id, row.title, row.completed, row.created_at, row.completed_at)
                for row in rows
            ]
            return (
                [item for item in items if not item.completed],
                [item for item in items if item.completed],
            )

    def add_task(self, profile_id: int, title: str) -> int:
        clean_title = title.strip()
        if not clean_title:
            raise ValueError("Task title is required.")
        if len(clean_title) > 200:
            raise ValueError("Task title must be 200 characters or fewer.")
        with self.storage.sessions.begin() as session:
            self._require_profile(session, profile_id)
            task = Task(
                profile_id=profile_id, title=clean_title, completed=False, created_at=utc_now()
            )
            session.add(task)
            session.flush()
            return task.id

    def toggle_task(self, profile_id: int, task_id: int) -> None:
        with self.storage.sessions.begin() as session:
            task = session.scalar(
                select(Task).where(Task.id == task_id, Task.profile_id == profile_id)
            )
            if task is None:
                raise ValueError("Task not found.")
            task.completed = not task.completed
            task.completed_at = utc_now() if task.completed else None

    def delete_task(self, profile_id: int, task_id: int) -> None:
        with self.storage.sessions.begin() as session:
            task = session.scalar(
                select(Task).where(Task.id == task_id, Task.profile_id == profile_id)
            )
            if task is None:
                raise ValueError("Task not found.")
            session.delete(task)
