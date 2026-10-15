"""A model can draft only one validated change, never execute it by itself."""

import json
from datetime import date, datetime

import pytest

from solar_forge_desktop.assistant_actions import AssistantActionService, parse_proposal
from solar_forge_desktop.assistant_settings import AssistantSettings, AssistantSettingsStore
from solar_forge_desktop.calendar import CalendarService
from solar_forge_desktop.storage import Storage
from solar_forge_desktop.tasks import TaskService


def setup_action_service(tmp_path):
    storage = Storage(tmp_path / "family.db")
    owner = storage.default_profile_id()
    member = storage.create_profile("Member")
    settings = AssistantSettingsStore(tmp_path / "config")
    settings.save(member, AssistantSettings(True, model="local", include_tasks=True,
                                            include_calendar=True))
    return storage, owner, member, settings, AssistantActionService(storage, settings, member)


def test_create_task_requires_approval_and_is_single_use(tmp_path, monkeypatch) -> None:
    storage, _, member, _, service = setup_action_service(tmp_path)
    class FakeClient:
        def __init__(self, _settings):
            pass

        def ask(self, _system, _prompt):
            return json.dumps({"operation": "create_task", "title": "Buy milk",
                               "due_at": "2026-10-16T18:00", "visibility": "private"})

    monkeypatch.setattr("solar_forge_desktop.assistant_actions.LocalModelClient", FakeClient)
    proposal = service.propose("Add buy milk on Friday", date(2026, 10, 14))
    assert "Buy milk" in proposal.preview(member)
    assert TaskService(storage).list_tasks(member)[0] == []
    task_id = service.approve(proposal)
    assert TaskService(storage).get_task(member, task_id).title == "Buy milk"
    with pytest.raises(ValueError, match="already handled"):
        service.approve(proposal)
    storage.close()


def test_update_rechecks_owner_and_stale_record(tmp_path) -> None:
    storage, owner, member, _, service = setup_action_service(tmp_path)
    tasks = TaskService(storage)
    other_id = tasks.add_task(owner, "Shared", "household")
    mine_id = tasks.add_task(member, "My task")
    with pytest.raises(ValueError, match="only your own"):
        parse_proposal(json.dumps({"operation": "update_task", "task_id": other_id,
                                   "title": "Changed", "due_at": None}),
                       (f"Task #{other_id}: Shared",), tasks, member)
    proposal = parse_proposal(json.dumps({"operation": "update_task", "task_id": mine_id,
                                          "title": "Changed", "due_at": None}),
                              (f"Task #{mine_id}: My task",), tasks, member)
    tasks.set_due_at(member, mine_id, datetime(2026, 10, 20, 9))
    with pytest.raises(ValueError, match="changed since"):
        service.approve(proposal)
    assert tasks.get_task(member, mine_id).title == "My task"
    storage.close()


def test_create_event_and_reject(tmp_path) -> None:
    storage, _, member, _, service = setup_action_service(tmp_path)
    proposal = parse_proposal(json.dumps({
        "operation": "create_event", "title": "Dentist", "category": "Personal",
        "starts_at": "2026-10-20T10:00", "ends_at": "2026-10-20T11:00",
        "visibility": "private",
    }), (), TaskService(storage), member)
    service.reject(proposal)
    with pytest.raises(ValueError, match="already handled"):
        service.approve(proposal)
    approved = parse_proposal(json.dumps({
        "operation": "create_event", "title": "Dentist", "category": "Personal",
        "starts_at": "2026-10-20T10:00", "ends_at": "2026-10-20T11:00",
        "visibility": "private",
    }), (), TaskService(storage), member)
    event_id = service.approve(approved)
    assert CalendarService(storage).get(member, event_id).title == "Dentist"
    storage.close()


@pytest.mark.parametrize("raw", [
    '{"operation":"create_task","title":"x","due_at":null,"visibility":"private",'
    '"extra":"surprise"}',
    '{"operation":"create_task","title":"x","title":"y",'
    '"due_at":null,"visibility":"private"}',
    '[{"operation":"create_task"}]',
    '{"operation":"update_task","task_id":true,"title":"x","due_at":null}',
    '{"operation":"create_event","title":"x","category":"Personal",'
    '"starts_at":"2026-10-20T10:00","ends_at":"2026-10-20T09:00",'
    '"visibility":"private"}',
    '```json\n{"operation":"create_task"}\n```',
])
def test_malformed_or_unapproved_model_output_is_rejected(tmp_path, raw) -> None:
    storage = Storage(tmp_path / "family.db")
    with pytest.raises(ValueError):
        parse_proposal(raw, (), TaskService(storage), storage.default_profile_id())
    storage.close()
