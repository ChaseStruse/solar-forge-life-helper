"""The local assistant sees only explicitly selected, authorized records."""

from datetime import date, datetime

import pytest

from solar_forge_desktop.assistant import AssistantService
from solar_forge_desktop.assistant_settings import (
    AssistantSettings,
    AssistantSettingsStore,
    validate_endpoint,
)
from solar_forge_desktop.calendar import CalendarService
from solar_forge_desktop.local_models import LocalModelClient
from solar_forge_desktop.storage import Storage
from solar_forge_desktop.tasks import TaskService


@pytest.mark.parametrize("endpoint", [
    "https://127.0.0.1:11434", "http://example.com:11434",
    "http://192.168.1.2:11434", "http://127.0.0.1:11434/other",
    "http://user:pass@127.0.0.1:11434", "http://127.0.0.1:11434?next=elsewhere",
    "http://127.0.0.1:11434#part", "http://127.0.0.1", "http://127.0.0.1:0",
])
def test_endpoint_rejects_nonlocal_or_ambiguous_origins(endpoint: str) -> None:
    with pytest.raises(ValueError):
        validate_endpoint(endpoint)


def test_settings_are_disabled_and_separate_for_each_member(tmp_path) -> None:
    store = AssistantSettingsStore(tmp_path)
    assert store.load(1) == AssistantSettings()
    enabled = AssistantSettings(True, "ollama", "http://127.0.0.1:11434", "local-model",
                                True, False)
    store.save(1, enabled)
    assert store.load(1) == enabled
    assert store.load(2) == AssistantSettings()
    assert (tmp_path / "assistant-profile-1.json").stat().st_mode & 0o077 == 0
    with pytest.raises(ValueError, match="category"):
        store.save(2, AssistantSettings(True, model="local-model"))


def test_assistant_sends_only_selected_visible_records(monkeypatch, tmp_path) -> None:
    storage = Storage(tmp_path / "family.db")
    owner = storage.default_profile_id()
    member = storage.create_profile("Member")
    tasks = TaskService(storage)
    tasks.add_task(owner, "Owner private medicine", due_at=datetime(2026, 10, 15, 9))
    tasks.add_task(owner, "Shared groceries", visibility="household",
                   due_at=datetime(2026, 10, 16, 17))
    tasks.add_task(member, "Member private task", due_at=datetime(2026, 10, 17, 12))
    calendar = CalendarService(storage)
    calendar.save(owner, "Owner private appointment", None, "Personal",
                  datetime(2026, 10, 16, 10), datetime(2026, 10, 16, 11))
    calendar.save(owner, "Shared household meeting", None, "Home",
                  datetime(2026, 10, 18, 10), datetime(2026, 10, 18, 11),
                  visibility="household")
    settings = AssistantSettingsStore(tmp_path / "config")
    settings.save(member, AssistantSettings(True, "ollama", "http://127.0.0.1:11434",
                                            "local-model", True, False))
    calls = []

    class FakeClient:
        def __init__(self, _settings):
            pass

        def ask(self, system, user):
            calls.append((system, user))
            return "The shared groceries are due Friday."

    monkeypatch.setattr("solar_forge_desktop.assistant.LocalModelClient", FakeClient)
    service = AssistantService(storage, settings, member)
    reply = service.ask("What is due this week?", date(2026, 10, 14))
    assert "Shared groceries" in calls[0][1]
    assert "Member private task" in calls[0][1]
    assert "Owner private medicine" not in calls[0][1]
    assert "Shared household meeting" not in calls[0][1]
    assert "Owner private appointment" not in calls[0][1]
    assert reply.records and reply.answer

    settings.save(member, AssistantSettings(True, "ollama", "http://127.0.0.1:11434",
                                            "local-model", False, True))
    service.ask("What is planned?", date(2026, 10, 14))
    assert "Shared household meeting" in calls[1][1]
    assert "Shared groceries" not in calls[1][1]
    assert "Owner private appointment" not in calls[1][1]
    storage.close()


def test_disabled_assistant_never_contacts_model(monkeypatch, tmp_path) -> None:
    storage = Storage(tmp_path / "family.db")
    profile = storage.default_profile_id()

    def unexpected_client(_settings):
        raise AssertionError("Disabled assistant contacted a model")

    monkeypatch.setattr("solar_forge_desktop.assistant.LocalModelClient", unexpected_client)
    with pytest.raises(ValueError, match="Enable"):
        AssistantService(storage, AssistantSettingsStore(tmp_path / "config"), profile).ask(
            "What is due?"
        )
    storage.close()


def test_question_retrieves_named_later_event_without_private_record(
        monkeypatch, tmp_path) -> None:
    storage = Storage(tmp_path / "family.db")
    owner = storage.default_profile_id()
    member = storage.create_profile("Member")
    calendar = CalendarService(storage)
    calendar.save(owner, "Dentist private appointment", None, "Personal",
                  datetime(2026, 12, 1, 9), datetime(2026, 12, 1, 10))
    calendar.save(member, "Dentist checkup", None, "Personal",
                  datetime(2026, 12, 2, 9), datetime(2026, 12, 2, 10))
    settings = AssistantSettingsStore(tmp_path / "config")
    settings.save(member, AssistantSettings(True, model="local", include_calendar=True))
    calls = []

    class FakeClient:
        def __init__(self, _settings):
            pass

        def ask(self, system, user):
            calls.append((system, user))
            return "Your dentist checkup is December 2 at 9:00."

    monkeypatch.setattr("solar_forge_desktop.assistant.LocalModelClient", FakeClient)
    reply = AssistantService(storage, settings, member).ask(
        "When is my dentist checkup?", date(2026, 10, 14)
    )
    assert "Dentist checkup" in calls[0][1]
    assert "Dentist private appointment" not in calls[0][1]
    assert "2026-12-02T09:00" in calls[0][1]
    assert "selected_records" in calls[0][1]
    assert "may omit other records" in calls[0][0]
    assert reply.records
    storage.close()


@pytest.mark.parametrize("provider,models_path,chat_path,models_response,chat_response", [
    ("ollama", "/api/tags", "/api/chat", {"models": [{"name": "local-model"}]},
     {"message": {"content": "A local answer."}}),
    ("llama.cpp", "/v1/models", "/v1/chat/completions",
     {"data": [{"id": "local-model"}]},
     {"choices": [{"message": {"content": "A local answer."}}]}),
])
def test_model_adapters_use_expected_local_api(monkeypatch, provider, models_path,
                                               chat_path, models_response,
                                               chat_response) -> None:
    import json

    calls = []

    class Response:
        def __init__(self, body):
            self.body = body

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def read(self, _size):
            return json.dumps(self.body).encode()

    class Opener:
        def open(self, request, timeout):
            calls.append((request, timeout))
            return Response(models_response if len(calls) == 1 else chat_response)

    monkeypatch.setattr("solar_forge_desktop.local_models.build_opener",
                        lambda *_handlers: Opener())
    client = LocalModelClient(AssistantSettings(True, provider,
                                                 "http://127.0.0.1:11434",
                                                 "local-model", True, False))
    assert client.models() == ("local-model",)
    assert client.ask("system", "user") == "A local answer."
    assert calls[0][0].full_url == "http://127.0.0.1:11434" + models_path
    assert calls[0][0].get_method() == "GET"
    assert calls[1][0].full_url == "http://127.0.0.1:11434" + chat_path
    assert calls[1][0].get_method() == "POST"
    payload = json.loads(calls[1][0].data)
    assert payload["messages"] == [{"role": "system", "content": "system"},
                                   {"role": "user", "content": "user"}]
    assert payload["stream"] is False
