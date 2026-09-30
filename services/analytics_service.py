"""Small, transparent aggregations used by the teacher dashboard."""

from __future__ import annotations

from collections import Counter, defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Any

from config import DASHBOARD_WINDOW_MINUTES
from services.storage_service import iter_all_events


def _event_timestamp(event: dict[str, Any]) -> datetime | None:
    """Parse an event timestamp and always return an aware UTC datetime."""
    try:
        timestamp = datetime.fromisoformat(event["timestamp"])
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        return timestamp.astimezone(timezone.utc)
    except (KeyError, TypeError, ValueError):
        return None


def _within_window(event: dict[str, Any], minutes: int) -> bool:
    """Return True when an event belongs to the selected classroom window.

    ``minutes == 0`` is the explicit dashboard value for "all history". In
    that mode no timestamp cut-off is applied.
    """
    if minutes == 0:
        return True
    timestamp = _event_timestamp(event)
    if timestamp is None:
        return False
    return timestamp >= datetime.now(timezone.utc) - timedelta(minutes=minutes)


def _filtered_student_messages(
    tutor_id: str | None,
    minutes: int,
    course_id: str | None,
) -> list[dict[str, Any]]:
    """Return student messages for the selected course/time/tutor filters."""
    messages = [
        event for event in iter_all_events()
        if event.get("event_type") == "student_message"
        and _within_window(event, minutes)
        and (not course_id or event.get("course_id") == course_id)
    ]
    if tutor_id:
        messages = [event for event in messages if event.get("tutor_id") == tutor_id]
    return messages

def _question_drilldown(
    messages: list[dict[str, Any]],
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """Pair classified questions with answers and group them by analytics field.

    The dashboard counters are useful for situational awareness, but a teacher
    also needs to inspect the evidence behind a category.  We therefore pair
    each selected ``student_message`` with the next ``tutor_message`` from the
    same session.  Pairing is performed from existing JSONL logs only; opening
    a category never causes an OpenAI request.

    A deque is used per session rather than a single pending item.  In normal
    UI use only one question is waiting at a time, but the queue keeps this
    robust if several messages happen to be logged before their answers.
    """
    # ``iter_all_events`` returns newly decoded dictionaries, so object IDs from
    # ``messages`` cannot be reused in another call.  A stable signature based
    # on fields written with every student event is therefore used instead.
    selected_signatures = {
        (
            event.get("session_id"),
            event.get("timestamp"),
            event.get("student_id"),
            event.get("message"),
        )
        for event in messages
    }

    paired_questions: list[dict[str, Any]] = []
    pending_by_session: dict[str, deque[dict[str, Any]]] = defaultdict(deque)

    events = sorted(iter_all_events(), key=lambda event: event.get("timestamp", ""))
    for event in events:
        session_id = str(event.get("session_id", ""))
        event_type = event.get("event_type")

        if event_type == "student_message":
            signature = (
                event.get("session_id"),
                event.get("timestamp"),
                event.get("student_id"),
                event.get("message"),
            )
            if signature not in selected_signatures:
                continue

            item = {
                "timestamp": event.get("timestamp", ""),
                "session_id": session_id,
                "student_id": event.get("student_id", "?"),
                "tutor_id": event.get("tutor_id"),
                "activity_id": event.get("activity_id"),
                "question": event.get("message", ""),
                "answer": "",
                "classification": event.get("classification", {}) or {},
            }
            paired_questions.append(item)
            pending_by_session[session_id].append(item)

        elif event_type == "tutor_message" and pending_by_session[session_id]:
            pending = pending_by_session[session_id].popleft()
            pending["answer"] = event.get("answer", "")

    grouped: dict[str, dict[str, list[dict[str, Any]]]] = {
        "topics": defaultdict(list),
        "misconceptions": defaultdict(list),
        "problems": defaultdict(list),
    }

    field_map = {
        "topics": "topic",
        "misconceptions": "possible_misconception",
        "problems": "problem_type",
    }
    for item in paired_questions:
        classification = item.get("classification", {}) or {}
        for group_name, field_name in field_map.items():
            value = classification.get(field_name)
            # A missing misconception is not an analytics category: only
            # questions for which the classifier actually detected a possible
            # misconception belong in this panel. Other fields keep "unknown".
            if group_name == "misconceptions" and not value:
                continue
            category = str(value or "unknown")
            grouped[group_name][category].append(item)

    # Newest questions first inside every category. Convert defaultdicts to
    # ordinary dictionaries before passing them to Jinja / JSON serializers.
    return {
        group_name: {
            category: list(reversed(items))
            for category, items in categories.items()
        }
        for group_name, categories in grouped.items()
    }


def classroom_summary(
    tutor_id: str | None = None,
    window_minutes: int | None = None,
    course_id: str | None = None,
) -> dict[str, Any]:
    """Aggregate selected classified student messages for situational awareness.

    Tutor, time window and class are independent filters.  When a class is
    selected, every metric on the dashboard refers to that class, not only the
    student table.  The returned ``drilldown`` uses the very same message set,
    so the number shown for a category always matches its clickable evidence.
    """
    minutes = window_minutes if window_minutes is not None else DASHBOARD_WINDOW_MINUTES
    messages = _filtered_student_messages(tutor_id, minutes, course_id)

    topics = Counter()
    misconceptions = Counter()
    problems = Counter()
    active_students = set()
    alerts: list[dict[str, Any]] = []

    for event in messages:
        classification = event.get("classification", {}) or {}
        topics[classification.get("topic", "unknown")] += 1
        misconception = classification.get("possible_misconception")
        if misconception:
            misconceptions[str(misconception)] += 1
        problems[classification.get("problem_type", "unknown")] += 1
        active_students.add(event.get("student_id", "?"))

        if classification.get("teacher_attention") or event.get("moderation_flagged"):
            alerts.append(
                {
                    "timestamp": event.get("timestamp"),
                    "student_id": event.get("student_id"),
                    "topic": classification.get("topic"),
                    "reason": classification.get("teacher_attention_reason")
                    or "Moderation flag",
                }
            )

    alerts = list(reversed(alerts[-20:]))

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_minutes": minutes,
        "course_id": course_id,
        "message_count": len(messages),
        "active_students": len(active_students),
        "topics": topics.most_common(10),
        "misconceptions": misconceptions.most_common(10),
        "problems": problems.most_common(10),
        "alerts": alerts,
        "drilldown": _question_drilldown(messages),
    }
