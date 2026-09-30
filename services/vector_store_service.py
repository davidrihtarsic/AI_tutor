"""Synchronise local Markdown knowledge with persistent OpenAI Vector Stores.

Design principle:
    local Markdown = source of truth
    OpenAI Vector Store = replaceable search index

The generated ``data/config/vector_stores.json`` is intentionally ignored by
Git because Vector Store and File IDs belong to one OpenAI installation.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from openai import OpenAI

from config import OPENAI_API_KEY, TUTORS_DIR, VECTOR_STORE_CONFIG
from services.tutor_service import get_tutor, knowledge_files


def _client() -> OpenAI:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY ni nastavljen. Kopiraj .env.example v .env.")
    return OpenAI(api_key=OPENAI_API_KEY)


def _load_config() -> dict[str, Any]:
    if not VECTOR_STORE_CONFIG.exists():
        return {}
    return json.loads(VECTOR_STORE_CONFIG.read_text(encoding="utf-8"))


def _save_config(config: dict[str, Any]) -> None:
    VECTOR_STORE_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    VECTOR_STORE_CONFIG.write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def get_vector_store_id(tutor_id: str) -> str | None:
    return _load_config().get(tutor_id, {}).get("vector_store_id")


def _wait_until_processed(client: OpenAI, vector_store_id: str, file_id: str) -> None:
    """Wait until OpenAI has chunked and indexed a newly attached file."""
    for _ in range(60):
        item = client.vector_stores.files.retrieve(
            vector_store_id=vector_store_id,
            file_id=file_id,
        )
        if item.status == "completed":
            return
        if item.status == "failed":
            raise RuntimeError(f"Indeksiranje datoteke {file_id} ni uspelo: {item.last_error}")
        time.sleep(1)
    raise TimeoutError(f"Datoteka {file_id} po 60 s še ni pripravljena.")


def _remove_remote_file(client: OpenAI, vector_store_id: str, file_id: str) -> None:
    """Detach an old file and then try to delete the underlying File object.

    Cleanup of the underlying File object is best-effort. If it fails, the
    important part (removing stale knowledge from this Vector Store) has still
    been attempted.
    """
    try:
        client.vector_stores.files.delete(
            vector_store_id=vector_store_id,
            file_id=file_id,
        )
    except Exception:
        pass

    try:
        client.files.delete(file_id)
    except Exception:
        pass


def sync_tutor(tutor_id: str) -> dict[str, Any]:
    """Create/update one tutor's persistent Vector Store.

    Only new, changed, and removed Markdown files are touched. SHA-256 hashes
    make the comparison deterministic and independent of modification times.
    """
    tutor = get_tutor(tutor_id)
    if not tutor:
        raise ValueError(f"Neznan tutor: {tutor_id}")

    client = _client()
    config = _load_config()
    state = config.setdefault(tutor_id, {"vector_store_id": None, "files": {}})

    if not state.get("vector_store_id"):
        vector_store = client.vector_stores.create(name=f"AI Classroom Tutor - {tutor['name']}")
        state["vector_store_id"] = vector_store.id
        _save_config(config)

    vector_store_id = state["vector_store_id"]
    remote_files: dict[str, Any] = state.setdefault("files", {})

    local: dict[str, dict[str, str]] = {}
    for path in knowledge_files(tutor_id):
        relative = path.relative_to(TUTORS_DIR / tutor_id).as_posix()
        local[relative] = {"sha256": _sha256(path), "absolute": str(path)}

    added: list[str] = []
    updated: list[str] = []
    removed: list[str] = []
    unchanged: list[str] = []

    # New and changed files.
    for relative, local_info in local.items():
        previous = remote_files.get(relative)
        if previous and previous.get("sha256") == local_info["sha256"]:
            unchanged.append(relative)
            continue

        path = Path(local_info["absolute"])
        with path.open("rb") as handle:
            uploaded = client.files.create(file=handle, purpose="assistants")

        client.vector_stores.files.create(
            vector_store_id=vector_store_id,
            file_id=uploaded.id,
        )
        _wait_until_processed(client, vector_store_id, uploaded.id)

        # Only remove the old version after the replacement is ready.
        if previous and previous.get("file_id"):
            _remove_remote_file(client, vector_store_id, previous["file_id"])
            updated.append(relative)
        else:
            added.append(relative)

        remote_files[relative] = {
            "sha256": local_info["sha256"],
            "file_id": uploaded.id,
        }
        _save_config(config)

    # Files deleted from the local source of truth must disappear remotely too.
    for relative in list(remote_files):
        if relative not in local:
            file_id = remote_files[relative].get("file_id")
            if file_id:
                _remove_remote_file(client, vector_store_id, file_id)
            del remote_files[relative]
            removed.append(relative)
            _save_config(config)

    return {
        "tutor_id": tutor_id,
        "vector_store_id": vector_store_id,
        "added": added,
        "updated": updated,
        "removed": removed,
        "unchanged": unchanged,
    }
