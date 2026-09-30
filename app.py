"""Web application for a classroom AI tutor prototype.

Run locally with:
    uvicorn app:app --reload

Version 0.2 changes the interaction model substantially:
1. Students log in only with nickname + password.
2. Students do NOT choose tutor or activity.
3. The teacher controls one active tutor/activity combination for everybody.
4. Every student message reads the current teacher configuration, therefore a
   change applies to all currently logged-in students on their next message.

This remains a local teaching/research prototype, not a production identity
system. Student passwords are intentionally stored as plain text; see README.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import socket

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from config import (
    BASE_DIR,
    CHAT_HISTORY_MESSAGES,
    DISPLAY_HISTORY_MESSAGES,
    PORT,
    SESSION_SECRET,
    TEACHER_PIN,
)
from models import ChatRequest, ChatResponse
from services.analytics_service import classroom_summary
from services.classroom_service import (
    get_active_course_id, get_classroom_config, set_active_course,
    set_chat_enabled, update_classroom_config,
)
from services.course_service import (
    configured_courses, courses_for_student, enroll_student, get_course, load_courses,
    registration_course_for_code, set_registration_open, student_ids_for_course, upsert_course,
)
from services.openai_service import (
    classify_learning_evidence,
    classify_message,
    generate_tutor_answer,
    moderate_text,
)
from services.storage_service import (
    append_event,
    create_session,
    get_session_metadata,
    recent_dialogue_for_revision,
    student_display_history,
    student_question_history,
    load_student_state,
    update_student_state,
    didactic_events_for_course,
    mark_microcheck_asked,
)
from services.tutor_service import (
    discover_tutors,
    get_tutor,
    load_activity,
    load_topics,
    load_tutor_instructions,
)
from services.user_service import (
    authenticate_student, create_student, get_user, load_users,
)
from services.presence_service import remove_student, student_is_active, touch_student
from services.vector_store_service import get_vector_store_id, sync_tutor

app = FastAPI(title="AI Classroom Tutor", version="0.2.0")
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


def _local_network_ip() -> str:
    """Return the IPv4 address normally used to reach this computer on the LAN."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # UDP connect selects the local interface; no packet needs to be sent.
        sock.connect(("8.8.8.8", 80))
        return str(sock.getsockname()[0])
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "127.0.0.1"
    finally:
        sock.close()


@app.on_event("startup")
async def print_classroom_urls() -> None:
    """Print convenient student and teacher LAN links when the server starts."""
    ip = _local_network_ip()
    base_url = f"http://{ip}:{PORT}"
    print("\n" + "=" * 58)
    print(f"  Ucenec:   {base_url}/")
    print(f"  Ucitelj:  {base_url}/teacher/login")
    print("=" * 58 + "\n")


def teacher_authenticated(request: Request) -> bool:
    """Return True when the current browser has passed the teacher PIN."""
    return bool(request.session.get("teacher_authenticated"))


def teacher_required(request: Request) -> None:
    """Protect teacher-only POST/API endpoints."""
    if not teacher_authenticated(request):
        raise HTTPException(status_code=401, detail="Teacher login required")


def student_nickname(request: Request) -> str | None:
    """Return nickname associated with the current browser session."""
    value = request.session.get("student_nickname")
    return str(value) if value else None


# ---------------------------------------------------------------------------
# Student interface
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    """Show only the student login form.

    Tutor/activity selection intentionally does not appear here. The active
    pedagogical configuration belongs to the teacher.
    """
    active_course_id = get_active_course_id()
    active_course = get_course(active_course_id) if active_course_id else None
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "error": None,
            "nickname": student_nickname(request),
            "active_course": active_course,
        },
    )


@app.post("/register", response_class=HTMLResponse)
def student_register(
    request: Request,
    nickname: str = Form(...),
    course_code: str = Form(...),
    password: str = Form(...),
):
    """Self-register a pupil using a teacher-provided class code."""
    nickname = nickname.strip()
    active_course_id = get_active_course_id()
    active_course = get_course(active_course_id) if active_course_id else None
    if not active_course:
        return templates.TemplateResponse(
            request=request, name="index.html",
            context={"error": "Učitelj še ni aktiviral tečaja.", "nickname": nickname, "register_open": True, "active_course": None},
            status_code=403,
        )

    course = registration_course_for_code(course_code)
    if not course or str(course.get("id")) != str(active_course_id):
        return templates.TemplateResponse(
            request=request, name="index.html",
            context={"error": "Registracijska koda ni veljavna za trenutno aktivni tečaj ali pa je vpis zaprt.", "nickname": nickname, "register_open": True, "active_course": active_course},
            status_code=400,
        )
    try:
        user = authenticate_student(nickname, password)
        if user is None:
            if get_user(nickname):
                raise ValueError("Uporabniško ime že obstaja, vendar geslo ni pravilno.")
            create_student(nickname, password)
        enroll_student(nickname, str(course["id"]))
    except ValueError as exc:
        return templates.TemplateResponse(
            request=request, name="index.html",
            context={"error": str(exc), "nickname": nickname, "register_open": True, "active_course": active_course},
            status_code=400,
        )

    request.session["student_nickname"] = nickname
    touch_student(nickname)
    request.session["student_course_id"] = str(course["id"])
    session = create_session(nickname, str(course["id"]))
    request.session["student_chat_session_id"] = session["session_id"]
    return RedirectResponse(url=f"/chat/{session['session_id']}", status_code=303)


@app.post("/login", response_class=HTMLResponse)
def student_login(
    request: Request,
    nickname: str = Form(...),
    password: str = Form(...),
):
    """Authenticate a student and create a fresh chat session."""
    nickname = nickname.strip()
    user = authenticate_student(nickname, password)

    if not user:
        active_course_id = get_active_course_id()
        active_course = get_course(active_course_id) if active_course_id else None
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={"error": "Napačno uporabniško ime ali geslo.", "nickname": nickname, "active_course": active_course},
            status_code=401,
        )

    # The teacher chooses the course currently being taught. A student never
    # chooses the course at login; this prevents accidental mixing of course data.
    active_course_id = get_active_course_id()
    active_course = get_course(active_course_id) if active_course_id else None
    if not active_course:
        return templates.TemplateResponse(
            request=request, name="index.html",
            context={"error": "Učitelj še ni aktiviral tečaja.", "nickname": nickname, "active_course": None},
            status_code=403,
        )

    enrolled_ids = {str(c["id"]) for c in courses_for_student(nickname)}
    if str(active_course_id) not in enrolled_ids:
        return templates.TemplateResponse(
            request=request, name="index.html",
            context={
                "error": f"Nisi vpisan v trenutno aktivni tečaj {active_course.get('name', active_course_id)}.",
                "nickname": nickname,
                "active_course": active_course,
            },
            status_code=403,
        )

    request.session["student_nickname"] = nickname
    touch_student(nickname)
    course_id = str(active_course_id)
    request.session["student_course_id"] = course_id
    session = create_session(nickname, course_id)
    request.session["student_chat_session_id"] = session["session_id"]
    return RedirectResponse(url=f"/chat/{session['session_id']}", status_code=303)


@app.get("/courses", response_class=HTMLResponse)
def choose_course_page(request: Request):
    """Legacy endpoint: course choice now belongs exclusively to the teacher."""
    return RedirectResponse(url="/", status_code=303)


@app.post("/courses")
def choose_course(request: Request, course_id: str = Form(...)):
    """Legacy endpoint kept only so old bookmarks/forms fail safely."""
    return RedirectResponse(url="/", status_code=303)


@app.post("/logout")
def student_logout(request: Request):
    """Log out only the student identity; keep teacher auth if same browser."""
    nickname = student_nickname(request)
    if nickname:
        remove_student(nickname)
    request.session.pop("student_nickname", None)
    request.session.pop("student_chat_session_id", None)
    request.session.pop("student_course_id", None)
    return RedirectResponse(url="/", status_code=303)


@app.get("/chat/{session_id}", response_class=HTMLResponse)
def chat_page(request: Request, session_id: str):
    """Render the generic student chatbot page.

    The page deliberately does not reveal or let the learner choose the active
    tutor/activity. Those are controlled centrally by the teacher.
    """
    nickname = student_nickname(request)
    if not nickname:
        return RedirectResponse(url="/", status_code=303)

    session = get_session_metadata(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # A learner must not be able to open another learner's chat merely by
    # knowing its URL/session id.
    if session.get("student_id") != nickname:
        raise HTTPException(status_code=403, detail="This is not your session")

    # Display history is intentionally broader than the AI context.  A learner
    # can see recent conversations after logging in again, while the model still
    # receives only the bounded dialogue from the current classroom revision.
    course_id = str(session.get("course_id", ""))
    if course_id not in {str(c["id"]) for c in courses_for_student(nickname)}:
        raise HTTPException(status_code=403, detail="Nisi vpisan v ta tečaj")
    request.session["student_course_id"] = course_id
    display_history = student_display_history(nickname, course_id, max_messages=DISPLAY_HISTORY_MESSAGES)

    # The chat header shows the teacher-controlled tutor/activity.  These values
    # are informational only; the backend still re-reads the classroom config
    # for every submitted message.
    classroom = get_classroom_config(course_id)
    active_tutor = get_tutor(classroom.get("tutor_id")) if classroom.get("tutor_id") else None
    active_activity_name = "Splošni pogovor"
    if active_tutor and classroom.get("activity_id"):
        active_activity_name = next(
            (
                item["name"]
                for item in active_tutor.get("activities", [])
                if item.get("id") == classroom.get("activity_id")
            ),
            classroom.get("activity_id"),
        )

    return templates.TemplateResponse(
        request=request,
        name="chat.html",
        context={
            "session": session,
            "nickname": nickname,
            "display_history": display_history,
            "tutor_name": active_tutor["name"] if active_tutor else "Ni izbran",
            "activity_name": active_activity_name,
            "course_name": (get_course(course_id) or {}).get("name", course_id),
            "learning_profile": _student_learning_profile(nickname, course_id),
        },
    )


@app.get("/api/classroom-status")
def classroom_status(request: Request):
    """Return the current teacher-controlled tutor/activity for the chat header."""
    if not student_nickname(request):
        raise HTTPException(status_code=401, detail="Student login required")

    course_id = request.session.get("student_course_id")
    if not course_id: raise HTTPException(status_code=400, detail="Course not selected")
    classroom = get_classroom_config(str(course_id))
    tutor = get_tutor(classroom.get("tutor_id")) if classroom.get("tutor_id") else None
    activity_name = "Splošni pogovor"
    if tutor and classroom.get("activity_id"):
        activity_name = next(
            (
                item["name"]
                for item in tutor.get("activities", [])
                if item.get("id") == classroom.get("activity_id")
            ),
            classroom.get("activity_id"),
        )

    return {
        "tutor_name": tutor["name"] if tutor else "Ni izbran",
        "activity_name": activity_name,
        "revision": int(classroom.get("revision", 1)),
        "chat_enabled": bool(classroom.get("chat_enabled", True)),
        "learning_profile": _student_learning_profile(
            student_nickname(request), str(course_id)
        ),
    }



def _adaptive_scaffolding(topic_state: dict, evidence_type: str) -> dict[str, str]:
    """Choose a deterministic scaffolding mode from Learner Model v3.

    The policy deliberately uses broad bands and accumulated didactic events
    rather than treating the learner estimates as precise scores.
    """
    understanding = float(topic_state.get("understanding_estimate", 0.5))
    progress = float(topic_state.get("progress_estimate", 0.5))
    independence = float(topic_state.get("independence_estimate", 0.5))
    understanding_weight = float(topic_state.get("understanding_evidence_weight", 0.0) or 0.0)

    open_events = {
        str(event.get("type"))
        for event in topic_state.get("didactic_events", []) or []
        if not event.get("resolved", False)
    }

    if "possible_misconception" in open_events or "stagnation" in open_events:
        mode = "rebuild"
        reason = "Persistent conceptual difficulty or stagnation detected."
    elif evidence_type == "repeated_question" or "stuck_loop" in open_events:
        mode = "guided"
        reason = "The learner appears stuck and needs a different route, not the same explanation again."
    elif evidence_type == "solution_seeking_without_attempt" or "dependency_risk" in open_events:
        mode = "fading"
        reason = "Understanding is developing, but support should be faded to strengthen independence."
    elif (
        evidence_type in {"advanced_question", "knowledge_transfer", "independent_debugging"}
        or (understanding >= 0.72 and progress >= 0.62 and independence >= 0.62)
    ):
        mode = "challenge"
        reason = "The learner is ready for less support and a more demanding transfer or reasoning step."
    elif understanding_weight >= 0.8 and understanding <= 0.42:
        mode = "rebuild"
        reason = "There is meaningful evidence of weak understanding of the current topic."
    elif understanding < 0.60 or progress < 0.48:
        mode = "guided"
        reason = "The learner benefits from structured hints and one manageable next step."
    else:
        mode = "balanced"
        reason = "No strong signal requires unusually high or low support."

    return {"mode": mode, "reason": reason}

@app.post("/api/chat", response_model=ChatResponse)
def api_chat(request: Request, payload: ChatRequest):
    """Complete one pedagogical turn using the CURRENT teacher configuration."""
    nickname = student_nickname(request)
    if not nickname:
        raise HTTPException(status_code=401, detail="Student login required")

    touch_student(nickname)
    session = get_session_metadata(payload.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.get("student_id") != nickname:
        raise HTTPException(status_code=403, detail="This is not your session")
    course_id = str(session.get("course_id", ""))
    if course_id not in {str(c["id"]) for c in courses_for_student(nickname)}:
        raise HTTPException(status_code=403, detail="Nisi vpisan v ta tečaj")

    # Critical design choice: tutor/activity are read NOW, not from the session
    # metadata created when the pupil logged in. Teacher changes therefore apply
    # to all active pupils starting with their next submitted message.
    classroom = get_classroom_config(course_id)
    if not classroom.get("chat_enabled", True):
        raise HTTPException(
            status_code=423,
            detail="Učitelj je začasno ustavil pogovor z AI tutorjem.",
        )
    tutor_id = classroom.get("tutor_id")
    activity_id = classroom.get("activity_id")
    classroom_revision = int(classroom.get("revision", 1))

    tutor = get_tutor(tutor_id) if tutor_id else None
    if not tutor:
        raise HTTPException(
            status_code=503,
            detail="Učitelj še ni izbral veljavnega tutorja.",
        )

    # Only dialogue from the CURRENT revision is sent back to the model. The
    # browser still shows the old messages, but changing tutor/activity creates
    # a clean pedagogical context boundary on the AI side.
    history = recent_dialogue_for_revision(
        payload.session_id,
        CHAT_HISTORY_MESSAGES,
        classroom_revision,
    )

    try:
        moderation_flagged = moderate_text(payload.message)
        classification = classify_message(
            tutor_name=tutor["name"],
            message=payload.message,
            recent_history=history,
            allowed_topics=load_topics(tutor_id),
        )

        if moderation_flagged:
            classification.teacher_attention = True
            if not classification.teacher_attention_reason:
                classification.teacher_attention_reason = (
                    "Moderation model flagged the message."
                )

        prior_questions = student_question_history(
            student_id=nickname,
            course_id=course_id,
            tutor_id=tutor_id,
            max_questions=40,
        )
        same_topic_history = [
            item
            for item in prior_questions
            if (item.get("classification", {}) or {}).get("topic")
            == classification.topic
        ][:6]
        same_topic_history.reverse()

        learning_evidence = classify_learning_evidence(
            tutor_name=tutor["name"],
            topic=classification.topic,
            message=payload.message,
            understanding_signal=classification.understanding_signal,
            recent_topic_history=same_topic_history,
        )

        append_event(
            payload.session_id,
            {
                "event_type": "student_message",
                "session_id": payload.session_id,
                "student_id": nickname,
                "course_id": course_id,
                "tutor_id": tutor_id,
                "activity_id": activity_id,
                "classroom_revision": classroom_revision,
                "message": payload.message,
                "classification": classification.model_dump(),
                "learning_evidence": learning_evidence.model_dump(),
                "moderation_flagged": moderation_flagged,
            },
        )

        student_state = update_student_state(
            student_id=nickname,
            course_id=course_id,
            tutor_id=tutor_id,
            topic=classification.topic,
            understanding_signal=classification.understanding_signal,
            learning_evidence=learning_evidence.model_dump(),
        )

        current_topic_state = (
            student_state.get("courses", {})
            .get(course_id, {})
            .get("tutors", {})
            .get(tutor_id, {})
            .get("topics", {})
            .get(classification.topic, {})
        )
        microcheck_due = bool(current_topic_state.get("microcheck_due", False))
        scaffolding = _adaptive_scaffolding(
            current_topic_state, learning_evidence.evidence_type
        )

        answer = generate_tutor_answer(
            tutor_instructions=load_tutor_instructions(tutor_id),
            activity_instructions=load_activity(tutor_id, activity_id),
            student_state=student_state,
            classification=classification,
            history=history,
            message=payload.message,
            vector_store_id=get_vector_store_id(tutor_id),
            microcheck_due=microcheck_due,
            scaffolding=scaffolding,
        )
        if microcheck_due:
            mark_microcheck_asked(
                nickname, course_id, tutor_id, classification.topic
            )

        append_event(
            payload.session_id,
            {
                "event_type": "tutor_message",
                "session_id": payload.session_id,
                "student_id": nickname,
                "course_id": course_id,
                "tutor_id": tutor_id,
                "activity_id": activity_id,
                "classroom_revision": classroom_revision,
                "answer": answer,
                "response_strategy": classification.response_strategy,
                "scaffolding_mode": scaffolding["mode"],
                "scaffolding_reason": scaffolding["reason"],
            },
        )

        return ChatResponse(
            answer=answer,
            classification=classification,
            moderation_flagged=moderation_flagged,
        )

    except Exception as exc:
        append_event(
            payload.session_id,
            {
                "event_type": "system_error",
                "session_id": payload.session_id,
                "student_id": nickname,
                "course_id": course_id,
                "tutor_id": tutor_id,
                "activity_id": activity_id,
                "classroom_revision": classroom_revision,
                "error": str(exc),
            },
        )
        raise HTTPException(status_code=500, detail=f"AI service error: {exc}") from exc


@app.post("/api/presence")
def student_presence(request: Request):
    """Refresh the logged-in learner's presence timestamp."""
    nickname = student_nickname(request)
    if not nickname:
        raise HTTPException(status_code=401, detail="Student login required")
    touch_student(nickname)
    return {"ok": True}


def _student_learning_profile(student_id: str, course_id: str | None) -> dict:
    """Return a student-facing five-level profile derived from LM v3.

    Only development above the neutral 0.50 prior is shown. A dimension with
    no evidence is marked as uncertain rather than being presented as a score.
    """
    stats = _course_learning_stats(student_id, course_id)

    def dimension(value: float, evidence_weight: float) -> dict:
        if evidence_weight <= 0:
            return {"level": 0, "uncertain": True}
        if value <= 0.5:
            level = 0
        else:
            level = min(5, max(1, int((value - 0.5) * 10 + 0.999999)))
        return {"level": level, "uncertain": False}

    return {
        "understanding": dimension(stats["understanding"], stats.get("understanding_weight", 0.0)),
        "progress": dimension(stats["progress"], stats.get("progress_weight", 0.0)),
        "independence": dimension(stats["independence"], stats.get("independence_weight", 0.0)),
    }


# ---------------------------------------------------------------------------
# Teacher interface
# ---------------------------------------------------------------------------

@app.get("/teacher/login", response_class=HTMLResponse)
def teacher_login_page(request: Request):
    if teacher_authenticated(request):
        return RedirectResponse(url="/teacher", status_code=303)
    return templates.TemplateResponse(
        request=request, name="teacher_login.html", context={"error": None}
    )


@app.post("/teacher/login", response_class=HTMLResponse)
def teacher_login(request: Request, pin: str = Form(...)):
    if pin == TEACHER_PIN:
        request.session["teacher_authenticated"] = True
        return RedirectResponse(url="/teacher", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="teacher_login.html",
        context={"error": "Napačen PIN."},
        status_code=401,
    )


@app.post("/teacher/logout")
def teacher_logout(request: Request):
    request.session.pop("teacher_authenticated", None)
    return RedirectResponse(url="/teacher/login", status_code=303)


def _course_learning_stats(student_id: str, course_id: str | None) -> dict:
    """Aggregate Learner Model v3 values for one student in one course.

    The compact dashboard values are evidence-weighted across all topics in
    the active course. Topic-level values remain available for the expanded
    student detail. A neutral 0.50 is shown when no evidence exists yet.
    """
    empty = {
        "understanding": 0.5,
        "progress": 0.5,
        "independence": 0.5,
        "observations": 0,
        "evidence_observations": 0,
        "understanding_weight": 0.0,
        "progress_weight": 0.0,
        "independence_weight": 0.0,
        "topics": [],
    }
    if not course_id:
        return empty

    state = load_student_state(student_id)
    course_state = state.get("courses", {}).get(str(course_id), {})
    tutors = course_state.get("tutors", {})

    topic_rows = []
    for tutor_id, tutor_state in tutors.items():
        for topic_id, topic_state in tutor_state.get("topics", {}).items():
            topic_rows.append({
                "tutor_id": str(tutor_id),
                "topic_id": str(topic_id),
                "understanding": float(topic_state.get("understanding_estimate", 0.5)),
                "progress": float(topic_state.get("progress_estimate", 0.5)),
                "independence": float(topic_state.get("independence_estimate", 0.5)),
                "observations": int(topic_state.get("observations", 0) or 0),
                "evidence_observations": int(topic_state.get("evidence_observations", 0) or 0),
                "understanding_weight": float(topic_state.get("understanding_evidence_weight", 0.0) or 0.0),
                "progress_weight": float(topic_state.get("progress_evidence_weight", 0.0) or 0.0),
                "independence_weight": float(topic_state.get("independence_evidence_weight", 0.0) or 0.0),
            })

    def weighted(axis: str, weight_key: str) -> float:
        total_weight = sum(row[weight_key] for row in topic_rows)
        if total_weight <= 0:
            return 0.5
        return sum(row[axis] * row[weight_key] for row in topic_rows) / total_weight

    topic_rows.sort(key=lambda row: (-row["evidence_observations"], row["topic_id"].casefold()))
    return {
        "understanding": weighted("understanding", "understanding_weight"),
        "progress": weighted("progress", "progress_weight"),
        "independence": weighted("independence", "independence_weight"),
        "observations": sum(row["observations"] for row in topic_rows),
        "evidence_observations": sum(row["evidence_observations"] for row in topic_rows),
        "understanding_weight": sum(row["understanding_weight"] for row in topic_rows),
        "progress_weight": sum(row["progress_weight"] for row in topic_rows),
        "independence_weight": sum(row["independence_weight"] for row in topic_rows),
        "topics": topic_rows,
    }


@app.get("/teacher", response_class=HTMLResponse)
def teacher_dashboard(
    request: Request,
    minutes: int | None = None,
):
    """Teacher dashboard for the currently active course.

    The teacher's active course is the operational classroom context: it
    determines which learners can start new sessions and which course is
    shown in the live analytics.  Analytics therefore needs only a time
    window; it does not maintain a second course/tutor selection that could
    be confused with the course currently being taught.
    """
    if not teacher_authenticated(request):
        return RedirectResponse(url="/teacher/login", status_code=303)

    tutors = discover_tutors()
    courses = load_courses()
    active_course_id = get_active_course_id()
    active_course = get_course(active_course_id) if active_course_id else None
    classroom = get_classroom_config(active_course_id) if active_course_id else {
        "tutor_id": None, "activity_id": None, "chat_enabled": True,
        "revision": 1, "updated_at": "",
    }

    # Dashboard time windows. Longer periods are expressed in minutes so the
    # existing query parameter remains backwards compatible. A value of 0 is a
    # deliberate sentinel meaning "all available history".
    time_windows = [
        {"value": 30, "label": "30 min"},
        {"value": 60, "label": "60 min"},
        {"value": 120, "label": "120 min"},
        {"value": 240, "label": "240 min"},
        {"value": 480, "label": "480 min"},
        {"value": 1440, "label": "24 h"},
        {"value": 7 * 24 * 60, "label": "1 teden"},
        {"value": 30 * 24 * 60, "label": "1 mesec"},
        {"value": 90 * 24 * 60, "label": "3 mesece"},
        {"value": 365 * 24 * 60, "label": "1 leto"},
        {"value": 0, "label": "Vse"},
    ]
    allowed_window_values = {item["value"] for item in time_windows}
    selected_window = minutes if minutes in allowed_window_values else None

    # Analytics always follows the course that the teacher is currently
    # conducting.  With no active course we intentionally use an impossible
    # course id so that the dashboard shows zeroes instead of silently mixing
    # data from every course.  Tutor changes inside one course remain visible
    # in the same course analytics, which is useful for later comparison.
    analytics_course_id = active_course_id or "__no_active_course__"
    summary = classroom_summary(None, selected_window, analytics_course_id)

    tutor_status = [
        {
            "id": item["id"],
            "name": item["name"],
            "vector_store_id": get_vector_store_id(item["id"]),
        }
        for item in tutors
    ]

    # Only learners enrolled in the active course belong in the live student
    # list. If no course is active the list should be empty, not all accounts.
    active_course_students = student_ids_for_course(active_course_id) if active_course_id else set()

    # Build the live student list once and keep currently active learners at
    # the top. Within each presence group, sort alphabetically by nickname so
    # the ordering remains predictable for the teacher.
    dashboard_users = []
    for user in load_users():
        nickname = str(user.get("nickname", ""))
        if nickname not in (active_course_students or set()):
            continue
        dashboard_users.append(
            {
                **user,
                "active": student_is_active(nickname),
                "learning": _course_learning_stats(nickname, active_course_id),
                "didactic_events": didactic_events_for_course(nickname, active_course_id),
                "questions": student_question_history(
                    nickname,
                    max_questions=100,
                    tutor_id=None,
                    course_id=active_course_id,
                    # ``0`` means "all history" and therefore no lower
                    # timestamp boundary should be applied.
                    since=(
                        None
                        if summary["window_minutes"] == 0
                        else datetime.now(timezone.utc)
                        - timedelta(minutes=summary["window_minutes"])
                    ),
                ),
            }
        )

    dashboard_users.sort(
        key=lambda user: (
            not bool(user.get("active")),
            str(user.get("nickname", "")).casefold(),
        )
    )

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "tutors": tutors,
            "selected_window": summary["window_minutes"],
            "time_windows": time_windows,
            "summary": summary,
            "tutor_status": tutor_status,
            "classroom": classroom,
            "active_course_id": active_course_id,
            "active_course": active_course,
            "course_classrooms": {str(c["id"]): get_classroom_config(str(c["id"])) for c in courses},
            "courses": courses,
            "selected_course": active_course_id,
            "course_settings": courses,
            # Plain-text passwords are intentionally visible to the teacher in
            # this trusted-LAN prototype so forgotten passwords are recoverable.
            "users": dashboard_users,
        },
    )


@app.post("/teacher/courses")
def teacher_save_course(
    request: Request,
    course_id: str = Form(...),
    course_name: str = Form(""),
    registration_code: str = Form(...),
):
    """Create a class or change its self-registration code."""
    teacher_required(request)
    try:
        upsert_course(course_id, course_name, registration_code, True)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse(url="/teacher", status_code=303)


@app.post("/teacher/courses/registration")
def teacher_toggle_course_registration(
    request: Request,
    course_id: str = Form(...),
    registration_open: str = Form(...),
):
    """Open or close first-time registration for one class."""
    teacher_required(request)
    try:
        set_registration_open(course_id, registration_open == "true")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse(url="/teacher", status_code=303)


@app.post("/teacher/classroom")
def teacher_set_classroom(
    request: Request,
    course_id: str = Form(...),
    tutor_id: str = Form(...),
    activity_id: str = Form(""),
):
    """Change tutor/activity for ALL learners starting with their next message."""
    teacher_required(request)
    try:
        if not get_course(course_id):
            raise ValueError("Izbrani tečaj ne obstaja.")
        set_active_course(course_id)
        update_classroom_config(course_id, tutor_id, activity_id or None)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse(url="/teacher", status_code=303)


@app.post("/teacher/chat-access")
def teacher_set_chat_access(
    request: Request,
    course_id: str = Form(...),
    chat_enabled: str = Form(...),
):
    """Temporarily allow/block new student messages for one course."""
    teacher_required(request)
    active_course_id = get_active_course_id()
    if course_id != active_course_id:
        raise HTTPException(status_code=409, detail="Pogovor lahko spreminjate le za trenutno aktivni tečaj.")
    set_chat_enabled(course_id, chat_enabled == "true")
    return RedirectResponse(url="/teacher", status_code=303)


@app.post("/teacher/sync/{tutor_id}")
def teacher_sync(request: Request, tutor_id: str):
    teacher_required(request)
    try:
        result = sync_tutor(tutor_id)
    except Exception as exc:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(exc)})
    return {"ok": True, "result": result}


@app.get("/health")
def health():
    """Small endpoint useful for local checks and later deployment."""
    return {"status":"ok","tutors":len(discover_tutors()),"courses":len(load_courses())}
