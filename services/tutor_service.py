"""Discovery and loading of tutor definitions stored on disk."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from config import TUTORS_DIR


def discover_tutors() -> list[dict[str, Any]]:
    """Discover tutor folders without requiring a central tutor registry.

    A folder becomes a tutor when it contains ``tutor.md``. Optional metadata
    lives in ``metadata.json`` because names, ordering and enabled flags are
    naturally structured data rather than prose.
    """
    tutors: list[dict[str, Any]] = []
    if not TUTORS_DIR.exists():
        return tutors

    for folder in sorted(p for p in TUTORS_DIR.iterdir() if p.is_dir()):
        tutor_file = folder / "tutor.md"
        if not tutor_file.exists():
            continue

        metadata_path = folder / "metadata.json"
        metadata: dict[str, Any] = {}
        if metadata_path.exists():
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

        if metadata.get("enabled", True) is False:
            continue

        tutors.append(
            {
                "id": folder.name,
                "name": metadata.get("name", folder.name.replace("_", " ").title()),
                "description": metadata.get("description", ""),
                "activities": discover_activities(folder.name),
            }
        )
    return tutors


def get_tutor(tutor_id: str) -> dict[str, Any] | None:
    return next((t for t in discover_tutors() if t["id"] == tutor_id), None)


def _parse_front_matter(text: str) -> tuple[dict[str, Any], str]:
    """Return YAML front matter and Markdown body.

    Activity files without front matter remain fully backwards compatible.
    Invalid YAML is reported with a clear error instead of silently changing
    the activity menu.
    """
    if not text.startswith("---\n"):
        return {}, text

    marker = "\n---\n"
    end = text.find(marker, 4)
    if end == -1:
        return {}, text

    raw_yaml = text[4:end]
    body = text[end + len(marker):]
    try:
        parsed = yaml.safe_load(raw_yaml) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"Neveljaven YAML v glavi aktivnosti: {exc}") from exc

    if not isinstance(parsed, dict):
        raise ValueError("YAML glava aktivnosti mora vsebovati preslikavo ključ-vrednost.")
    return parsed, body


def _activity_document(path: Path, tutor_id: str) -> dict[str, Any] | None:
    metadata, body = _parse_front_matter(path.read_text(encoding="utf-8"))

    if metadata.get("enabled", True) is False:
        return None

    declared_tutor = str(metadata.get("tutor", "")).strip()
    if declared_tutor and declared_tutor != tutor_id:
        return None

    activity_id = str(metadata.get("id") or path.stem).strip()
    if not activity_id:
        activity_id = path.stem

    title = str(
        metadata.get("title")
        or _markdown_title_from_text(body)
        or path.stem.replace("_", " ").title()
    ).strip()

    try:
        order = int(metadata.get("order", 9999))
    except (TypeError, ValueError):
        order = 9999

    return {
        "id": activity_id,
        "name": title,
        "title": title,
        "description": str(metadata.get("description", "")).strip(),
        "order": order,
        "tutor": tutor_id,
        "path": path,
        "body": body,
    }


def _activity_documents(tutor_id: str) -> list[dict[str, Any]]:
    folder = TUTORS_DIR / tutor_id / "activities"
    if not folder.exists():
        return []

    documents: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for path in sorted(folder.glob("*.md")):
        document = _activity_document(path, tutor_id)
        if document is None:
            continue
        activity_id = document["id"]
        if activity_id in seen_ids:
            raise ValueError(
                f"Podvojen id aktivnosti '{activity_id}' pri tutorju '{tutor_id}'."
            )
        seen_ids.add(activity_id)
        documents.append(document)

    documents.sort(key=lambda item: (item["order"], item["name"].casefold(), item["id"]))
    return documents


def discover_activities(tutor_id: str) -> list[dict[str, Any]]:
    """Return activity metadata used by teacher menus and validation."""
    return [
        {
            "id": item["id"],
            "name": item["name"],
            "title": item["title"],
            "description": item["description"],
            "order": item["order"],
            "tutor": item["tutor"],
        }
        for item in _activity_documents(tutor_id)
    ]


def _markdown_title_from_text(text: str) -> str | None:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None


def _markdown_title(path: Path) -> str | None:
    """Compatibility helper retained for older callers/tests."""
    metadata, body = _parse_front_matter(path.read_text(encoding="utf-8"))
    return str(metadata.get("title") or _markdown_title_from_text(body) or "").strip() or None


def load_tutor_instructions(tutor_id: str) -> str:
    path = TUTORS_DIR / tutor_id / "tutor.md"
    if not path.exists():
        raise FileNotFoundError(f"Tutor '{tutor_id}' nima datoteke tutor.md")
    return path.read_text(encoding="utf-8")


def load_activity(tutor_id: str, activity_id: str | None) -> str:
    """Load only the Markdown body of an activity selected by metadata id."""
    if not activity_id:
        return ""
    for document in _activity_documents(tutor_id):
        if document["id"] == activity_id:
            return document["body"]
    return ""


def knowledge_files(tutor_id: str) -> list[Path]:
    """Return Markdown files that belong in the tutor's Vector Store."""
    folder = TUTORS_DIR / tutor_id / "knowledge"
    if not folder.exists():
        return []
    return sorted(folder.rglob("*.md"))


def load_topics(tutor_id: str) -> list[dict[str, str]]:
    """Load the tutor-specific topic taxonomy used to stabilise analytics labels."""
    path = TUTORS_DIR / tutor_id / "topics.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [item for item in data if isinstance(item, dict) and item.get("id")]
