"""Permission-scoped household context for a selected local model."""

import re
from dataclasses import dataclass
from datetime import date, timedelta

from solar_forge_desktop.assistant_guidance import (
    QUESTION_INSTRUCTIONS,
    request_context,
    search_terms,
)
from solar_forge_desktop.assistant_settings import AssistantSettingsStore
from solar_forge_desktop.calendar import CalendarService
from solar_forge_desktop.calendar import occurrences as expand_occurrences
from solar_forge_desktop.local_models import LocalModelClient
from solar_forge_desktop.storage import Storage
from solar_forge_desktop.tasks import TaskService


@dataclass(frozen=True)
class AssistantReply:
    answer: str
    records: tuple[str, ...]


class AssistantService:
    def __init__(self, storage: Storage, settings: AssistantSettingsStore, profile_id: int):
        self.tasks = TaskService(storage)
        self.calendar = CalendarService(storage)
        self.settings = settings
        self.profile_id = profile_id

    def _records(self, today: date, include_tasks: bool,
                 include_calendar: bool, request: str = "") -> tuple[str, ...]:
        last = today + timedelta(days=13)
        records: list[str] = []
        terms = search_terms(request)
        if include_tasks:
            open_tasks, _ = self.tasks.list_tasks(self.profile_id)
            due = [task for task in open_tasks if task.due_at
                   and date.fromisoformat(task.due_at[:10]) <= last]
            due.sort(key=lambda task: (task.due_at or "", task.id))
            undated = [task for task in open_tasks if not task.due_at]
            selected = due[:30] + undated[:10]
            selected_ids = {task.id for task in selected}
            for task in self.tasks.find_owned_open_tasks(self.profile_id, terms):
                if task.id not in selected_ids:
                    selected.append(task)
                    selected_ids.add(task.id)
            match = re.search(r"\btask\s*#?(\d+)\b", request.casefold())
            if match:
                try:
                    task = self.tasks.get_task(self.profile_id, int(match.group(1)))
                except ValueError:
                    pass
                else:
                    if not task.completed and task.id not in selected_ids:
                        selected.append(task)
            for task in selected:
                due_text = task.due_at or "no due date"
                editable = "yes" if task.profile_id == self.profile_id else "no"
                records.append(f"Task #{task.id}: {task.title} | owner: "
                               f"#{task.profile_id} | editable: {editable} | "
                               f"due: {due_text} | {task.visibility}")
        if include_calendar:
            seen: set[tuple[int, str]] = set()
            occurrences = []
            for offset in (0, 7, 14):
                view = self.calendar.view(self.profile_id, today + timedelta(days=offset),
                                          mode="week")
                for day, items in view.days:
                    if not today <= day <= last:
                        continue
                    for item in items:
                        key = (item.event.id, item.starts_at.isoformat())
                        if key not in seen:
                            seen.add(key)
                            occurrences.append(item)
            occurrences.sort(key=lambda item: (item.starts_at, item.event.id))
            for item in occurrences[:40]:
                records.append(
                    f"Event #{item.event.id}: {item.event.title} | "
                    f"owner: #{item.event.profile_id} | "
                    f"start: {item.starts_at.isoformat(timespec='minutes')} | "
                    f"end: {item.ends_at.isoformat(timespec='minutes')} | "
                    f"{item.event.visibility}"
                )
            included_events = {item.event.id for item in occurrences[:40]}
            for event in self.calendar.find_events(self.profile_id, terms, today):
                if event.id in included_events:
                    continue
                if event.recurrence == "none":
                    start, end = event.starts_at, event.ends_at
                else:
                    upcoming = expand_occurrences(event, today, today + timedelta(days=365))
                    if not upcoming:
                        continue
                    start, end = upcoming[0].starts_at, upcoming[0].ends_at
                records.append(
                    f"Event #{event.id}: {event.title} | owner: #{event.profile_id} | "
                    f"start: {start.isoformat(timespec='minutes')} | "
                    f"end: {end.isoformat(timespec='minutes')} | "
                    f"repeat: {event.recurrence} | {event.visibility}"
                )
        return tuple(records)

    def ask(self, question: str, today: date | None = None) -> AssistantReply:
        settings = self.settings.load(self.profile_id)
        if not settings.enabled:
            raise ValueError("Enable the local assistant for this member first.")
        question = question.strip() if isinstance(question, str) else ""
        if not question or len(question) > 500:
            raise ValueError("Ask a question of 1 to 500 characters.")
        today = today or date.today()
        records = self._records(today, settings.include_tasks, settings.include_calendar,
                                question)
        if not records:
            return AssistantReply("No selected tasks or events were found for the next "
                                  "14 days.", ())
        categories = tuple(name for name, enabled in (
            ("tasks", settings.include_tasks), ("calendar", settings.include_calendar)
        ) if enabled)
        user = request_context(today, question, records, categories)
        answer = LocalModelClient(settings).ask(QUESTION_INSTRUCTIONS, user)
        return AssistantReply(answer, records)
