"""Central application configuration.

All values that may differ between installations are read from environment
variables. This keeps secrets and machine-specific settings out of Git.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Project root = directory that contains this file.
BASE_DIR = Path(__file__).resolve().parent

# Load variables from a local .env file when it exists.
load_dotenv(BASE_DIR / ".env")

# Directory layout.
TUTORS_DIR = BASE_DIR / "tutors"
DATA_DIR = BASE_DIR / "data"
SESSIONS_DIR = DATA_DIR / "sessions"
STUDENTS_DIR = DATA_DIR / "students"
CONFIG_DIR = DATA_DIR / "config"
VECTOR_STORE_CONFIG = CONFIG_DIR / "vector_stores.json"
CLASSROOM_CONFIG = CONFIG_DIR / "classroom.json"
CLASSROOM_EVENTS = CONFIG_DIR / "classroom_events.jsonl"
PRESENCE_FILE = CONFIG_DIR / "presence.json"
USERS_FILE = DATA_DIR / "users.json"
USERS_EXAMPLE_FILE = DATA_DIR / "users.example.json"
COURSES_FILE = DATA_DIR / "courses.json"
ENROLLMENTS_FILE = DATA_DIR / "enrollments.json"

# OpenAI configuration.
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
TUTOR_MODEL = os.getenv("OPENAI_TUTOR_MODEL", "gpt-5.6-luna")
CLASSIFIER_MODEL = os.getenv("OPENAI_CLASSIFIER_MODEL", "gpt-5.6-luna")
MODERATION_MODEL = os.getenv("OPENAI_MODERATION_MODEL", "omni-moderation-latest")

# Application behaviour.
CHAT_HISTORY_MESSAGES = int(os.getenv("CHAT_HISTORY_MESSAGES", "10"))
DISPLAY_HISTORY_MESSAGES = int(os.getenv("DISPLAY_HISTORY_MESSAGES", "60"))
DASHBOARD_WINDOW_MINUTES = int(os.getenv("DASHBOARD_WINDOW_MINUTES", "120"))
ACTIVE_STUDENT_SECONDS = int(os.getenv("ACTIVE_STUDENT_SECONDS", "180"))
TEACHER_PIN = os.getenv("TEACHER_PIN", "1234")
SESSION_SECRET = os.getenv("SESSION_SECRET", "development-secret-change-me")
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))

# Ensure runtime directories exist even on a fresh checkout.
for directory in (SESSIONS_DIR, STUDENTS_DIR, CONFIG_DIR):
    directory.mkdir(parents=True, exist_ok=True)
