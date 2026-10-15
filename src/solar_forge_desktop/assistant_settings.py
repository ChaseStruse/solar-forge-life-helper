"""Per-member, opt-in settings for the read-only local assistant."""

import ipaddress
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit


@dataclass(frozen=True)
class AssistantSettings:
    enabled: bool = False
    provider: str = "ollama"
    endpoint: str = "http://127.0.0.1:11434"
    model: str = ""
    include_tasks: bool = False
    include_calendar: bool = False


def validate_endpoint(value: str) -> str:
    """Accept only a literal loopback HTTP origin, never a proxy or LAN host."""
    if not isinstance(value, str):
        raise ValueError("Enter a local model address.")
    parsed = urlsplit(value.strip())
    try:
        address = ipaddress.ip_address(parsed.hostname or "")
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Use a loopback address such as http://127.0.0.1:11434.") from exc
    if (parsed.scheme != "http" or not address.is_loopback or port is None
            or parsed.username is not None or parsed.password is not None
            or parsed.path not in ("", "/") or parsed.query or parsed.fragment):
        raise ValueError("Use only a local HTTP address and port, with no path or credentials.")
    host = f"[{address}]" if address.version == 6 else str(address)
    return f"http://{host}:{port}"


def validate_settings(settings: AssistantSettings) -> AssistantSettings:
    if settings.provider not in {"ollama", "llama.cpp"}:
        raise ValueError("Choose Ollama or llama.cpp.")
    endpoint = validate_endpoint(settings.endpoint)
    model = settings.model.strip() if isinstance(settings.model, str) else ""
    if len(model) > 120 or any(ord(char) < 32 for char in model):
        raise ValueError("Enter a valid local model name.")
    if settings.enabled and not model:
        raise ValueError("Choose a model before enabling the assistant.")
    if settings.enabled and not (settings.include_tasks or settings.include_calendar):
        raise ValueError("Choose at least one record category for the assistant.")
    for field in (settings.enabled, settings.include_tasks, settings.include_calendar):
        if not isinstance(field, bool):
            raise ValueError("Assistant permissions must be on or off.")
    return AssistantSettings(settings.enabled, settings.provider, endpoint, model,
                             settings.include_tasks, settings.include_calendar)


class AssistantSettingsStore:
    def __init__(self, directory: Path):
        self.directory = directory

    def _path(self, profile_id: int) -> Path:
        if isinstance(profile_id, bool) or not isinstance(profile_id, int) or profile_id <= 0:
            raise ValueError("Invalid profile.")
        return self.directory / f"assistant-profile-{profile_id}.json"

    def load(self, profile_id: int) -> AssistantSettings:
        path = self._path(profile_id)
        if not path.exists():
            return AssistantSettings()
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(document, dict) or document.get("version") != 1:
                raise ValueError("Unsupported assistant settings format.")
            return validate_settings(AssistantSettings(
                document["enabled"], document["provider"], document["endpoint"],
                document["model"], document["include_tasks"], document["include_calendar"],
            ))
        except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError,
                ValueError) as exc:
            raise ValueError("Could not read this member's assistant settings.") from exc

    def save(self, profile_id: int, settings: AssistantSettings) -> None:
        settings = validate_settings(settings)
        path = self._path(profile_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(prefix=".assistant-", dir=path.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                os.chmod(temporary, 0o600)
                json.dump({"version": 1, **vars(settings)}, stream)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
