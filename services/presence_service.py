"""Very small file-based presence tracker for the teacher dashboard.

A successful login marks a learner as present. The chat page then sends a tiny
heartbeat request periodically.  This means the teacher sees ``DA`` only while
the learner has actually been present recently; simply having an account is not
enough.  Logging out removes presence immediately.

This is intentionally simple and transparent.  It is not a general-purpose
realtime presence system.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from config import ACTIVE_STUDENT_SECONDS, PRESENCE_FILE


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _load() -> dict[str, Any]:
    if not PRESENCE_FILE.exists():
        return {}
    try:
        data = json.loads(PRESENCE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _save(data: dict[str, Any]) -> None:
    PRESENCE_FILE.parent.mkdir(parents=True, exist_ok=True)
    PRESENCE_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def touch_student(nickname: str) -> None:
    """Mark a learner as recently present."""
    data = _load()
    data[nickname] = {"last_seen": _now().isoformat()}
    _save(data)


def remove_student(nickname: str) -> None:
    """Immediately mark a learner as no longer present."""
    data = _load()
    if nickname in data:
        del data[nickname]
        _save(data)


def student_is_active(nickname: str) -> bool:
    """Return True only when the last heartbeat is still fresh."""
    entry = _load().get(nickname, {})
    try:
        last_seen = datetime.fromisoformat(entry["last_seen"])
        if last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=timezone.utc)
    except (KeyError, TypeError, ValueError):
        return False
    return last_seen >= _now() - timedelta(seconds=ACTIVE_STUDENT_SECONDS)


def presence_snapshot() -> dict[str, bool]:
    """Return current active status for every nickname in the presence file."""
    return {nickname: student_is_active(nickname) for nickname in _load()}
