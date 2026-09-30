"""File-based persistence for sessions, events, and lightweight student state.

The project deliberately avoids SQLite. Human-readable JSON and append-only
JSONL files make it easy to inspect, archive, and analyse classroom data with
ordinary tools such as Python, pandas, R, jq, or even a text editor.
"""

from __future__ import annotations

import json
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import SESSIONS_DIR, STUDENTS_DIR


def utc_now_iso() -> str:
    """Return a timezone-aware timestamp suitable for logs."""
    return datetime.now(timezone.utc).isoformat()


def _safe_id(value: str) -> str:
    """Convert user-entered IDs into safe file-name fragments.

    This is intentionally conservative because student IDs become part of file
    paths. The original value is still stored inside the event itself.
    """
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip())
    return cleaned[:80] or "anonymous"


def create_session(student_id: str, course_id: str) -> dict[str, Any]:
    """Create a student chat session independent of tutor/activity.

    Tutor and activity are deliberately NOT stored here as authoritative state.
    They are read from the teacher-controlled classroom configuration for every
    new message, so changes apply immediately to all current students.
    """
    session_id = secrets.token_urlsafe(12)
    session = {
        "session_id": session_id,
        "student_id": student_id.strip(),
        "course_id": course_id.strip(),
        "started_at": utc_now_iso(),
    }
    _create_session_file(session)
    return session


def _session_files() -> list[Path]:
    return sorted(SESSIONS_DIR.glob("*/*.jsonl"))

def _find_session_file(session_id: str) -> Path | None:
    for path in _session_files():
        try:
            with path.open("r", encoding="utf-8") as handle:
                first = handle.readline().strip()
            if first and json.loads(first).get("session_id") == session_id:
                return path
        except (OSError, json.JSONDecodeError):
            continue
    return None

def _create_session_file(session: dict[str, Any]) -> Path:
    course_dir = SESSIONS_DIR / _safe_id(str(session["course_id"]))
    course_dir.mkdir(parents=True, exist_ok=True)
    started = datetime.fromisoformat(str(session["started_at"]))
    stem = started.strftime("%Y-%m-%d_%H%M")
    path = course_dir / f"{stem}.jsonl"
    suffix = 2
    while path.exists():
        path = course_dir / f"{stem}_{suffix:02d}.jsonl"
        suffix += 1
    payload = {"timestamp": utc_now_iso(), "event_type": "session_started", **session}
    path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")
    return path

def _session_file(session_id: str) -> Path:
    path = _find_session_file(session_id)
    if path is None:
        raise FileNotFoundError(f"Session not found: {session_id}")
    return path

def append_event(session_id: str, event: dict[str, Any]) -> None:
    """Append exactly one JSON object as one line.

    JSONL is safer than repeatedly rewriting a large JSON array and is very
    convenient for later stream processing.
    """
    payload = {"timestamp": utc_now_iso(), **event}
    with _session_file(session_id).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def load_session_events(session_id: str) -> list[dict[str, Any]]:
    """Find and read all events belonging to a session."""
    path = _find_session_file(session_id)
    if path is None:
        return []

    events: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


def get_session_metadata(session_id: str) -> dict[str, Any] | None:
    """Recover session metadata from the first event."""
    events = load_session_events(session_id)
    for event in events:
        if event.get("event_type") == "session_started":
            return event
    return None


def recent_dialogue(session_id: str, max_messages: int) -> list[dict[str, str]]:
    """Return recent user/assistant turns in Responses API message format."""
    dialogue: list[dict[str, str]] = []
    for event in load_session_events(session_id):
        if event.get("event_type") == "student_message":
            dialogue.append({"role": "user", "content": event.get("message", "")})
        elif event.get("event_type") == "tutor_message":
            dialogue.append({"role": "assistant", "content": event.get("answer", "")})
    return dialogue[-max_messages:]




def recent_dialogue_for_revision(
    session_id: str, max_messages: int, classroom_revision: int
) -> list[dict[str, str]]:
    """Return dialogue only from the current teacher configuration revision.

    When the teacher changes tutor or activity, the learner keeps seeing the
    same page, but the model must not silently inherit the previous pedagogical
    context. Filtering by revision creates that clean context boundary.
    """
    dialogue: list[dict[str, str]] = []
    for event in load_session_events(session_id):
        if event.get("classroom_revision") != classroom_revision:
            continue
        if event.get("event_type") == "student_message":
            dialogue.append({"role": "user", "content": event.get("message", "")})
        elif event.get("event_type") == "tutor_message":
            dialogue.append({"role": "assistant", "content": event.get("answer", "")})
    return dialogue[-max_messages:]


def student_display_history(student_id: str, course_id: str, max_messages: int = 60) -> list[dict[str, Any]]:
    """Return recent visible dialogue for one student across earlier sessions.

    This history is meant only for rendering the learner's chat window.  It is
    deliberately separate from ``recent_dialogue_for_revision``: showing old
    messages to the learner must not automatically inject them into the model
    context or increase API token use.

    Only normal student/tutor messages are returned; system errors, moderation
    metadata and other analytics events stay hidden from the learner.
    """
    dialogue: list[dict[str, Any]] = []

    for event in iter_all_events():
        if event.get("student_id") != student_id or event.get("course_id") != course_id:
            continue

        event_type = event.get("event_type")
        if event_type == "student_message":
            dialogue.append(
                {
                    "role": "student",
                    "text": event.get("message", ""),
                    "timestamp": event.get("timestamp", ""),
                }
            )
        elif event_type == "tutor_message":
            dialogue.append(
                {
                    "role": "assistant",
                    "text": event.get("answer", ""),
                    "timestamp": event.get("timestamp", ""),
                }
            )

    # JSONL files are normally already chronological, but sorting makes the
    # function robust when sessions span several day folders.
    dialogue.sort(key=lambda item: item.get("timestamp", ""))
    return dialogue[-max_messages:]

def _student_file(student_id: str) -> Path:
    return STUDENTS_DIR / f"{_safe_id(student_id)}.json"


def load_student_state(student_id: str) -> dict[str, Any]:
    path = _student_file(student_id)
    if not path.exists():
        return {"student_id": student_id, "courses": {}, "updated_at": utc_now_iso()}
    return json.loads(path.read_text(encoding="utf-8"))


def _weighted_estimate_update(
    old_value: float,
    old_weight: float,
    evidence_value: float | None,
    evidence_weight: float,
    *,
    prior_strength: float = 2.0,
) -> tuple[float, float]:
    """Update one 0..1 estimate while retaining a weak 0.5 prior."""
    if evidence_value is None or evidence_weight <= 0:
        return old_value, old_weight
    value = max(0.0, min(1.0, float(evidence_value)))
    weight = max(0.0, float(evidence_weight))
    effective_old_weight = prior_strength + old_weight
    new_value = (old_value * effective_old_weight + value * weight) / (
        effective_old_weight + weight
    )
    return max(0.0, min(1.0, new_value)), old_weight + weight



_DIDACTIC_EVENT_LABELS = {
    "stuck_loop": "Ponavljajoča se težava",
    "possible_misconception": "Možna napačna predstava",
    "dependency_risk": "Odvisnost od pomoči",
    "conceptual_progression": "Konceptualni napredek",
    "productive_experimentation": "Produktivno eksperimentiranje",
    "stagnation": "Zastoj v napredku",
}


def _upsert_didactic_event(
    topic_state: dict[str, Any],
    event_type: str,
    *,
    severity: str,
    reason: str,
) -> None:
    """Create or refresh one open didactic event of the same type."""
    events = topic_state.setdefault("didactic_events", [])
    now = utc_now_iso()
    for event in events:
        if event.get("type") == event_type and not event.get("resolved", False):
            event["severity"] = severity
            event["reason"] = reason[:300]
            event["updated_at"] = now
            return
    events.append(
        {
            "type": event_type,
            "label": _DIDACTIC_EVENT_LABELS[event_type],
            "severity": severity,
            "reason": reason[:300],
            "created_at": now,
            "updated_at": now,
            "resolved": False,
        }
    )


def _evaluate_didactic_events(topic_state: dict[str, Any], evidence_type: str) -> None:
    """Derive teacher-facing didactic events from accumulated v3 evidence."""
    counts = topic_state.get("evidence_types", {}) or {}
    observations = int(topic_state.get("observations", 0) or 0)
    understanding = float(topic_state.get("understanding_estimate", 0.5))
    progress = float(topic_state.get("progress_estimate", 0.5))
    independence = float(topic_state.get("independence_estimate", 0.5))

    if int(counts.get("repeated_question", 0) or 0) >= 2:
        _upsert_didactic_event(
            topic_state, "stuck_loop", severity="medium",
            reason="Učenec je pri isti temi večkrat ponovil podobno vprašanje brez jasnega novega koraka.",
        )
    negative = int(counts.get("explicit_negative", 0) or 0) + int(
        counts.get("check_answer_negative", 0) or 0
    )
    if negative >= 2:
        _upsert_didactic_event(
            topic_state, "possible_misconception", severity="high",
            reason="Pri isti temi se ponavlja dokaz napačnega konceptualnega razumevanja.",
        )
    if observations >= 5 and understanding >= 0.62 and independence <= 0.42:
        _upsert_didactic_event(
            topic_state, "dependency_risk", severity="medium",
            reason="Razumevanje je razmeroma dobro, samostojnost pa ostaja nizka.",
        )
    if evidence_type in {"advanced_question", "knowledge_transfer"}:
        _upsert_didactic_event(
            topic_state, "conceptual_progression", severity="positive",
            reason="Učenec je pokazal prehod k zahtevnejšemu konceptu ali prenos znanja.",
        )
    if evidence_type == "independent_debugging":
        _upsert_didactic_event(
            topic_state, "productive_experimentation", severity="positive",
            reason="Učenec je samostojno izvedel preizkus, diagnostiko ali izboljšavo rešitve.",
        )
    if observations >= 8 and progress <= 0.38:
        _upsert_didactic_event(
            topic_state, "stagnation", severity="high",
            reason="Po več interakcijah ostaja ocena napredka nizka.",
        )


def _microcheck_due(topic_state: dict[str, Any], evidence_type: str) -> bool:
    """Return True when a short diagnostic check would add useful evidence."""
    observations = int(topic_state.get("observations", 0) or 0)
    last_at = int(topic_state.get("last_microcheck_observation", -99) or -99)
    if observations - last_at < 4:
        return False

    understanding = float(topic_state.get("understanding_estimate", 0.5))
    counts = topic_state.get("evidence_types", {}) or {}
    negative = int(counts.get("explicit_negative", 0) or 0) + int(
        counts.get("check_answer_negative", 0) or 0
    )
    uncertain = 0.42 <= understanding <= 0.58 and observations >= 3
    misconception = negative >= 2
    repeated = evidence_type == "repeated_question"
    progression = evidence_type in {"advanced_question", "knowledge_transfer"}

    return uncertain or misconception or repeated or progression


def mark_microcheck_asked(
    student_id: str,
    course_id: str,
    tutor_id: str,
    topic: str,
) -> None:
    """Persist the cooldown marker after the tutor actually asks a micro-check."""
    state = load_student_state(student_id)
    topic_state = (
        state.get("courses", {})
        .get(course_id, {})
        .get("tutors", {})
        .get(tutor_id, {})
        .get("topics", {})
        .get(topic)
    )
    if not topic_state:
        return
    topic_state["last_microcheck_observation"] = int(topic_state.get("observations", 0) or 0)
    topic_state["last_microcheck_at"] = utc_now_iso()
    state["updated_at"] = utc_now_iso()
    _student_file(student_id).write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def didactic_events_for_course(student_id: str, course_id: str | None) -> list[dict[str, Any]]:
    """Return open didactic events for one learner in one course."""
    if not course_id:
        return []
    state = load_student_state(student_id)
    course = state.get("courses", {}).get(course_id, {})
    rows: list[dict[str, Any]] = []
    for tutor_id, tutor_state in (course.get("tutors", {}) or {}).items():
        for topic_id, topic_state in (tutor_state.get("topics", {}) or {}).items():
            for event in topic_state.get("didactic_events", []) or []:
                if event.get("resolved", False):
                    continue
                rows.append(
                    {
                        **event,
                        "tutor_id": tutor_id,
                        "topic_id": topic_id,
                    }
                )
    rows.sort(key=lambda item: str(item.get("updated_at", "")), reverse=True)
    return rows

def update_student_state(
    student_id: str,
    course_id: str,
    tutor_id: str,
    topic: str,
    understanding_signal: str = "neutral",
    learning_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Update an explainable three-axis formative learner model."""
    state = load_student_state(student_id)
    course_state = state.setdefault("courses", {}).setdefault(course_id, {"tutors": {}})
    tutor_state = course_state.setdefault("tutors", {}).setdefault(tutor_id, {"topics": {}})
    topic_state = tutor_state.setdefault("topics", {}).setdefault(
        topic,
        {
            "understanding_estimate": 0.5,
            "progress_estimate": 0.5,
            "independence_estimate": 0.5,
            "observations": 0,
            "evidence_observations": 0,
            "understanding_evidence_weight": 0.0,
            "progress_evidence_weight": 0.0,
            "independence_evidence_weight": 0.0,
            "evidence_types": {},
        },
    )

    if "understanding_estimate" not in topic_state:
        topic_state["understanding_estimate"] = float(
            topic_state.pop("support_estimate", 0.5)
        )
    topic_state.setdefault("progress_estimate", 0.5)
    topic_state.setdefault("independence_estimate", 0.5)
    topic_state.setdefault("observations", 0)
    topic_state.setdefault("evidence_observations", 0)
    topic_state.setdefault("understanding_evidence_weight", 0.0)
    topic_state.setdefault("progress_evidence_weight", 0.0)
    topic_state.setdefault("independence_evidence_weight", 0.0)
    topic_state.setdefault("evidence_types", {})

    evidence = learning_evidence or {}
    evidence_type = str(evidence.get("evidence_type", "neutral"))

    if not learning_evidence:
        if understanding_signal == "positive":
            evidence = {
                "evidence_type": "explicit_positive",
                "understanding_value": 1.0,
                "understanding_weight": 1.0,
            }
            evidence_type = "explicit_positive"
        elif understanding_signal == "negative":
            evidence = {
                "evidence_type": "explicit_negative",
                "understanding_value": 0.0,
                "understanding_weight": 1.0,
            }
            evidence_type = "explicit_negative"

    axes = (
        ("understanding", "understanding_estimate"),
        ("progress", "progress_estimate"),
        ("independence", "independence_estimate"),
    )
    moved_any_axis = False
    for prefix, estimate_key in axes:
        old = float(topic_state.get(estimate_key, 0.5))
        weight_key = f"{prefix}_evidence_weight"
        old_weight = float(topic_state.get(weight_key, 0.0))
        value = evidence.get(f"{prefix}_value")
        weight = float(evidence.get(f"{prefix}_weight", 0.0) or 0.0)
        new_value, new_weight = _weighted_estimate_update(
            old, old_weight, value, weight
        )
        topic_state[estimate_key] = round(new_value, 3)
        topic_state[weight_key] = round(new_weight, 3)
        if new_weight > old_weight:
            moved_any_axis = True

    topic_state["observations"] = int(topic_state.get("observations", 0)) + 1
    if moved_any_axis:
        topic_state["evidence_observations"] = int(
            topic_state.get("evidence_observations", 0)
        ) + 1
        counts = topic_state.setdefault("evidence_types", {})
        counts[evidence_type] = int(counts.get(evidence_type, 0)) + 1
        topic_state["last_evidence"] = {
            "type": evidence_type,
            "reason": str(evidence.get("reason", ""))[:300],
            "timestamp": utc_now_iso(),
        }

    for obsolete in (
        "positive_evidence",
        "negative_evidence",
        "legacy_evidence",
        "legacy_evidence_observations",
    ):
        topic_state.pop(obsolete, None)

    _evaluate_didactic_events(topic_state, evidence_type)
    topic_state["microcheck_due"] = _microcheck_due(topic_state, evidence_type)

    state["updated_at"] = utc_now_iso()
    _student_file(student_id).write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return state


def iter_all_events() -> list[dict[str, Any]]:
    """Read every JSONL event. Suitable for a small classroom prototype."""
    events: list[dict[str, Any]] = []
    for path in sorted(SESSIONS_DIR.glob("*/*.jsonl")):
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
    return events



def student_question_history(
    student_id: str,
    max_questions: int = 100,
    tutor_id: str | None = None,
    course_id: str | None = None,
    since: datetime | None = None,
) -> list[dict[str, Any]]:
    """Return a learner's questions paired with the corresponding tutor answer.

    Pairing uses chronological order inside each session.  A question remains
    visible even when an answer was not produced (for example after an API
    error), in which case ``answer`` is an empty string.
    """
    events = sorted(iter_all_events(), key=lambda e: e.get("timestamp", ""))
    questions: list[dict[str, Any]] = []
    pending_by_session: dict[str, dict[str, Any]] = {}

    for event in events:
        if event.get("student_id") != student_id:
            continue
        if course_id and event.get("course_id") != course_id:
            continue

        if since is not None:
            try:
                timestamp = datetime.fromisoformat(event.get("timestamp", ""))
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=timezone.utc)
                if timestamp < since:
                    continue
            except (TypeError, ValueError):
                continue

        if tutor_id and event.get("tutor_id") != tutor_id:
            continue

        session_id = str(event.get("session_id", ""))
        event_type = event.get("event_type")

        if event_type == "student_message":
            item = {
                "timestamp": event.get("timestamp", ""),
                "session_id": session_id,
                "tutor_id": event.get("tutor_id"),
                "activity_id": event.get("activity_id"),
                "question": event.get("message", ""),
                "answer": "",
                "classification": event.get("classification", {}) or {},
            }
            questions.append(item)
            pending_by_session[session_id] = item

        elif event_type == "tutor_message":
            pending = pending_by_session.get(session_id)
            if pending is not None and not pending.get("answer"):
                pending["answer"] = event.get("answer", "")
                pending_by_session.pop(session_id, None)

    return list(reversed(questions[-max_questions:]))
