"""Small HTTP adapters for model servers on this computer only."""

import json
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from solar_forge_desktop.assistant_settings import AssistantSettings, validate_settings

MAX_RESPONSE_BYTES = 1_000_000


class _NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


class LocalModelClient:
    def __init__(self, settings: AssistantSettings):
        self.settings = validate_settings(settings)
        self._opener = build_opener(ProxyHandler({}), _NoRedirects())

    def _request(self, path: str, payload: dict | None = None, timeout: int = 30) -> dict:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(
            self.settings.endpoint + path, data=data,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST" if data is not None else "GET",
        )
        try:
            with self._opener.open(request, timeout=timeout) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
        except HTTPError as exc:
            raise RuntimeError(f"Local model server returned HTTP {exc.code}.") from exc
        except (OSError, URLError) as exc:
            raise RuntimeError("Could not connect to the local model server.") from exc
        if len(raw) > MAX_RESPONSE_BYTES:
            raise RuntimeError("Local model response was too large.")
        try:
            result = json.loads(raw)
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("Local model server returned invalid JSON.") from exc
        if not isinstance(result, dict):
            raise RuntimeError("Local model server returned an invalid response.")
        return result

    def models(self) -> tuple[str, ...]:
        path = "/api/tags" if self.settings.provider == "ollama" else "/v1/models"
        result = self._request(path, timeout=5)
        rows = result.get("models") if self.settings.provider == "ollama" else result.get("data")
        if not isinstance(rows, list):
            raise RuntimeError("Local model server did not provide a model list.")
        key = "name" if self.settings.provider == "ollama" else "id"
        return tuple(row[key] for row in rows if isinstance(row, dict)
                     and isinstance(row.get(key), str))

    def ask(self, system: str, user: str) -> str:
        if not self.settings.model:
            raise ValueError("Choose a model first.")
        messages = [{"role": "system", "content": system},
                    {"role": "user", "content": user}]
        if self.settings.provider == "ollama":
            path = "/api/chat"
            payload = {"model": self.settings.model, "messages": messages, "stream": False}
        else:
            path = "/v1/chat/completions"
            payload = {"model": self.settings.model, "messages": messages,
                       "stream": False, "max_tokens": 700}
        result = self._request(path, payload, timeout=90)
        try:
            content = (result["message"]["content"] if self.settings.provider == "ollama"
                       else result["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("Local model server returned no answer.") from exc
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("Local model server returned an empty answer.")
        return content.strip()
