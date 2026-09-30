"""Teacher-controlled classroom configuration.

The application keeps one *active course* for new student logins.  Tutor,
activity and temporary chat availability are still stored independently per
course, so switching the active course never rewrites another course's state.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from config import CLASSROOM_CONFIG, CLASSROOM_EVENTS
from services.tutor_service import discover_tutors, get_tutor


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_course_config() -> dict[str, Any]:
    tutors = discover_tutors()
    return {
        "tutor_id": tutors[0]["id"] if tutors else None,
        "activity_id": None,
        "chat_enabled": True,
        "revision": 1,
        "updated_at": utc_now_iso(),
    }


def _load_all() -> dict[str, Any]:
    if not CLASSROOM_CONFIG.exists():
        return {"active_course_id": None, "courses": {}}

    data = json.loads(CLASSROOM_CONFIG.read_text(encoding="utf-8"))
    if "courses" not in data:
        return {"active_course_id": None, "courses": {}}  # legacy config is migrated explicitly

    data.setdefault("active_course_id", None)
    return data


def save_all(data: dict[str, Any]) -> None:
    CLASSROOM_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CLASSROOM_CONFIG.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def get_active_course_id() -> str | None:
    value = _load_all().get("active_course_id")
    return str(value) if value else None


def set_active_course(course_id: str | None) -> None:
    data = _load_all()
    previous = data.get("active_course_id")
    course_id = course_id.strip() if course_id else None
    data["active_course_id"] = course_id
    save_all(data)
    if previous != course_id:
        append_classroom_event(
            {
                "event_type": "active_course_changed",
                "old_course_id": previous,
                "new_course_id": course_id,
            }
        )


def get_classroom_config(course_id: str) -> dict[str, Any]:
    data = _load_all()
    config = data["courses"].get(course_id)
    if config is None:
        config = _default_course_config()
        data["courses"][course_id] = config
        save_all(data)
    else:
        # Backwards compatibility with v1.2 configs created before the chat lock.
        if "chat_enabled" not in config:
            config["chat_enabled"] = True
            data["courses"][course_id] = config
            save_all(data)
    return config


def update_classroom_config(course_id: str, tutor_id: str, activity_id: str | None) -> dict[str, Any]:
    tutor = get_tutor(tutor_id)
    if not tutor:
        raise ValueError("Izbrani tutor ne obstaja.")

    activity_id = activity_id or None
    if activity_id and activity_id not in {x["id"] for x in tutor["activities"]}:
        raise ValueError("Izbrana dejavnost ne pripada izbranemu tutorju.")

    data = _load_all()
    previous = data["courses"].get(course_id) or _default_course_config()
    changed = (
        previous.get("tutor_id") != tutor_id
        or previous.get("activity_id") != activity_id
    )
    config = {
        "tutor_id": tutor_id,
        "activity_id": activity_id,
        "chat_enabled": bool(previous.get("chat_enabled", True)),
        "revision": max(
            1,
            int(previous.get("revision", 0)) + (1 if changed else 0),
        ),
        "updated_at": utc_now_iso(),
    }
    data["courses"][course_id] = config
    save_all(data)

    if changed:
        append_classroom_event(
            {
                "event_type": "teaching_configuration_changed",
                "course_id": course_id,
                "old_tutor_id": previous.get("tutor_id"),
                "old_activity_id": previous.get("activity_id"),
                "new_tutor_id": tutor_id,
                "new_activity_id": activity_id,
                "revision": config["revision"],
            }
        )
    return config


def set_chat_enabled(course_id: str, enabled: bool) -> dict[str, Any]:
    """Allow or temporarily block new student messages for one course.

    This does not log students out and does not change the pedagogical revision;
    it is a classroom-attention control, not a change of tutor context.
    """
    data = _load_all()
    previous = data["courses"].get(course_id) or _default_course_config()
    previous_enabled = bool(previous.get("chat_enabled", True))
    previous["chat_enabled"] = bool(enabled)
    previous["updated_at"] = utc_now_iso()
    data["courses"][course_id] = previous
    save_all(data)

    if previous_enabled != bool(enabled):
        append_classroom_event(
            {
                "event_type": "student_chat_access_changed",
                "course_id": course_id,
                "chat_enabled": bool(enabled),
                "revision": int(previous.get("revision", 1)),
            }
        )
    return previous


def append_classroom_event(event: dict[str, Any]) -> None:
    CLASSROOM_EVENTS.parent.mkdir(parents=True, exist_ok=True)
    payload = {"timestamp": utc_now_iso(), **event}
    with CLASSROOM_EVENTS.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
