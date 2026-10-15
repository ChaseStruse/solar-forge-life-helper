"""Private local record of explicit assistant action decisions."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path


class AssistantAuditStore:
    def __init__(self, directory: Path, profile_id: int):
        self.path = directory / f"assistant-actions-profile-{profile_id}.jsonl"

    def record(self, token: str, decision: str, operation: str, fields: dict) -> None:
        if decision not in {"approved", "rejected", "failed"}:
            raise ValueError("Invalid assistant decision.")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(self.path, flags, 0o600)
        try:
            os.fchmod(descriptor, 0o600)
            entry = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                     "proposal": token, "decision": decision, "operation": operation,
                     "fields": fields}
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(json.dumps(entry, ensure_ascii=False) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
        except BaseException:
            try:
                os.close(descriptor)
            except OSError:
                pass
            raise

    def recent(self, limit: int = 20) -> tuple[dict, ...]:
        if not self.path.exists():
            return ()
        lines = self.path.read_text(encoding="utf-8").splitlines()[-limit:]
        return tuple(json.loads(line) for line in reversed(lines))
