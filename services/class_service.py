"""JSON-based classroom/section registration settings.

A teacher creates a class and a temporary registration code. Pupils use the
code only for their first registration; later logins use nickname + password.
"""
from __future__ import annotations

import json
from typing import Any

from config import CLASSES_FILE


def _normalise(value: str) -> str:
    return value.strip()


def load_class_settings() -> list[dict[str, Any]]:
    if not CLASSES_FILE.exists():
        return []
    data = json.loads(CLASSES_FILE.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("data/classes.json mora vsebovati JSON seznam oddelkov.")
    return [item for item in data if isinstance(item, dict)]


def save_class_settings(items: list[dict[str, Any]]) -> None:
    CLASSES_FILE.parent.mkdir(parents=True, exist_ok=True)
    CLASSES_FILE.write_text(
        json.dumps(items, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def configured_classes() -> list[str]:
    return sorted({str(item.get("class", "")).strip() for item in load_class_settings() if str(item.get("class", "")).strip()})


def registration_class_for_code(code: str) -> str | None:
    code = _normalise(code)
    if not code:
        return None
    for item in load_class_settings():
        if item.get("registration_open", False) and str(item.get("registration_code", "")).strip() == code:
            return str(item.get("class", "")).strip() or None
    return None


def upsert_class(class_id: str, registration_code: str, registration_open: bool = True) -> dict[str, Any]:
    class_id = _normalise(class_id)
    registration_code = _normalise(registration_code)
    if not class_id:
        raise ValueError("Vnesite oznako oddelka.")
    if not registration_code:
        raise ValueError("Vnesite registracijsko kodo.")

    items = load_class_settings()
    for item in items:
        if str(item.get("class", "")).strip() != class_id and str(item.get("registration_code", "")).strip() == registration_code:
            raise ValueError("Ta registracijska koda je že uporabljena pri drugem oddelku.")

    target = next((item for item in items if str(item.get("class", "")).strip() == class_id), None)
    if target is None:
        target = {"class": class_id}
        items.append(target)
    target["registration_code"] = registration_code
    target["registration_open"] = bool(registration_open)
    save_class_settings(items)
    return target


def set_registration_open(class_id: str, is_open: bool) -> None:
    items = load_class_settings()
    target = next((item for item in items if str(item.get("class", "")).strip() == class_id.strip()), None)
    if target is None:
        raise ValueError("Oddelek ne obstaja.")
    target["registration_open"] = bool(is_open)
    save_class_settings(items)
