#!/usr/bin/env python3
"""Safe merge importer for the historical ELORA26 data set.

Default behavior is DRY RUN. Nothing is changed unless --apply is supplied.
The script uses only the Python standard library.

Safety properties:
- never blindly overwrites data/users.json or data/classes.json;
- resolves username conflicts case-insensitively by creating a unique nickname;
- preserves an existing ELORA26 class configuration if one already exists;
- never overwrites an existing session file;
- merges student topic-state files when the same account is deliberately reused;
- creates a timestamped backup before changing existing files;
- writes JSON atomically where practical;
- records a persistent import manifest so the same import is not accidentally run twice.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

IMPORT_ID = "elora26_2026-05-30"
IMPORT_CLASS = "ELORA26"


def json_load(path: Path, default: Any) -> Any:
    if not path.exists():
        return copy.deepcopy(default)
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def atomic_json_write(path: Path, data: Any) -> None:
    """Write JSON through a temporary file and atomically replace destination."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


def directory_hash(path: Path) -> str:
    """Stable SHA-256 of all files in an import payload."""
    h = hashlib.sha256()
    for file in sorted(p for p in path.rglob("*") if p.is_file()):
        rel = file.relative_to(path).as_posix().encode("utf-8")
        h.update(rel)
        h.update(b"\0")
        with file.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        h.update(b"\0")
    return h.hexdigest()


def unique_nickname(base: str, occupied_casefold: set[str]) -> str:
    """Create a readable, deterministic nickname that does not collide."""
    candidate = f"{base}_elora26"
    if candidate.casefold() not in occupied_casefold:
        return candidate
    i = 2
    while True:
        candidate = f"{base}_elora26_{i}"
        if candidate.casefold() not in occupied_casefold:
            return candidate
        i += 1


def unique_session_id(base: str, sessions_dir: Path, reserved: set[str]) -> str:
    candidate = f"{base}_elora26"
    if candidate not in reserved and not (sessions_dir / f"{candidate}.jsonl").exists():
        return candidate
    i = 2
    while True:
        candidate = f"{base}_elora26_{i}"
        if candidate not in reserved and not (sessions_dir / f"{candidate}.jsonl").exists():
            return candidate
        i += 1


def transform_jsonl(source: Path, student_map: dict[str, str], new_session_id: str | None = None) -> bytes:
    """Rewrite student_id/session_id references while preserving all historical content."""
    out: list[str] = []
    old_session_id: str | None = None
    with source.open("r", encoding="utf-8") as f:
        for raw in f:
            if not raw.strip():
                continue
            event = json.loads(raw)
            if old_session_id is None:
                old_session_id = event.get("session_id")
            sid = event.get("student_id")
            if isinstance(sid, str) and sid in student_map:
                event["student_id"] = student_map[sid]
            if new_session_id is not None and event.get("session_id") == old_session_id:
                event["session_id"] = new_session_id
            out.append(json.dumps(event, ensure_ascii=False))
    return ("\n".join(out) + "\n").encode("utf-8")


def _normalize_v3_topic(entry: dict[str, Any]) -> dict[str, Any]:
    """Normalize a topic record to Learner Model v3.

    Historical topic states without genuine v3 evidence keep their observation
    count, but their old scalar estimate is not reused as v3 evidence.
    """
    normalized = {
        "understanding_estimate": float(entry.get("understanding_estimate", 0.5)),
        "progress_estimate": float(entry.get("progress_estimate", 0.5)),
        "independence_estimate": float(entry.get("independence_estimate", 0.5)),
        "observations": int(entry.get("observations", 0) or 0),
        "evidence_observations": int(entry.get("evidence_observations", 0) or 0),
        "understanding_evidence_weight": float(entry.get("understanding_evidence_weight", 0.0) or 0.0),
        "progress_evidence_weight": float(entry.get("progress_evidence_weight", 0.0) or 0.0),
        "independence_evidence_weight": float(entry.get("independence_evidence_weight", 0.0) or 0.0),
        "evidence_types": copy.deepcopy(entry.get("evidence_types", {})),
    }
    if entry.get("last_evidence"):
        normalized["last_evidence"] = copy.deepcopy(entry["last_evidence"])
    return normalized


def _merge_v3_axis(
    left: dict[str, Any],
    right: dict[str, Any],
    estimate_key: str,
    weight_key: str,
) -> tuple[float, float]:
    left_weight = float(left.get(weight_key, 0.0) or 0.0)
    right_weight = float(right.get(weight_key, 0.0) or 0.0)
    total_weight = left_weight + right_weight
    if total_weight <= 0:
        return 0.5, 0.0

    estimate = (
        float(left.get(estimate_key, 0.5)) * left_weight
        + float(right.get(estimate_key, 0.5)) * right_weight
    ) / total_weight
    return round(estimate, 4), round(total_weight, 4)


def _merge_v3_topic(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    left = _normalize_v3_topic(left)
    right = _normalize_v3_topic(right)

    understanding, understanding_weight = _merge_v3_axis(
        left, right, "understanding_estimate", "understanding_evidence_weight"
    )
    progress, progress_weight = _merge_v3_axis(
        left, right, "progress_estimate", "progress_evidence_weight"
    )
    independence, independence_weight = _merge_v3_axis(
        left, right, "independence_estimate", "independence_evidence_weight"
    )

    evidence_types: dict[str, int] = {}
    for source in (left.get("evidence_types", {}), right.get("evidence_types", {})):
        for evidence_type, count in source.items():
            key = str(evidence_type)
            evidence_types[key] = evidence_types.get(key, 0) + int(count or 0)

    merged = {
        "understanding_estimate": understanding,
        "progress_estimate": progress,
        "independence_estimate": independence,
        "observations": int(left.get("observations", 0)) + int(right.get("observations", 0)),
        "evidence_observations": int(left.get("evidence_observations", 0))
        + int(right.get("evidence_observations", 0)),
        "understanding_evidence_weight": understanding_weight,
        "progress_evidence_weight": progress_weight,
        "independence_evidence_weight": independence_weight,
        "evidence_types": evidence_types,
    }
    if right.get("last_evidence") or left.get("last_evidence"):
        merged["last_evidence"] = copy.deepcopy(
            right.get("last_evidence") or left.get("last_evidence")
        )
    return merged


def merge_student_models(existing: dict[str, Any], imported: dict[str, Any], target_student_id: str) -> dict[str, Any]:
    """Merge learner-state files using Learner Model v3 evidence weights."""
    result = copy.deepcopy(existing)
    result["student_id"] = target_student_id
    result.setdefault("tutors", {})

    for tutor_id, tutor_data in imported.get("tutors", {}).items():
        target_tutor = result["tutors"].setdefault(tutor_id, {})
        target_topics = target_tutor.setdefault("topics", {})
        for topic_id, imported_topic in tutor_data.get("topics", {}).items():
            if topic_id not in target_topics:
                target_topics[topic_id] = _normalize_v3_topic(imported_topic)
                continue

            target_topics[topic_id] = _merge_v3_topic(
                target_topics[topic_id], imported_topic
            )

    imported_updated = imported.get("updated_at")
    existing_updated = result.get("updated_at")
    if imported_updated and (not existing_updated or imported_updated > existing_updated):
        result["updated_at"] = imported_updated
    return result

def backup_file(source: Path, project_root: Path, backup_root: Path) -> None:
    if not source.exists():
        return
    rel = source.relative_to(project_root)
    dest = backup_root / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Safely merge ELORA26 historical conversations into AI Classroom Tutor.")
    parser.add_argument("--apply", action="store_true", help="Actually perform the merge. Without this flag, only a dry-run is shown.")
    parser.add_argument("--project-root", type=Path, default=None, help="Project directory. Defaults to the parent directory of scripts/.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    script_path = Path(__file__).resolve()
    project_root = (args.project_root.resolve() if args.project_root else script_path.parent.parent)
    payload_root = project_root / "imports" / IMPORT_ID
    payload_data = payload_root / "data"
    data_root = project_root / "data"

    users_path = data_root / "users.json"
    classes_path = data_root / "classes.json"
    students_dir = data_root / "students"
    sessions_dir = data_root / "sessions" / "2026-05-30"
    imports_state_dir = data_root / "imports"
    manifest_path = imports_state_dir / f"{IMPORT_ID}.json"

    if not payload_data.exists():
        print(f"ERROR: Import payload not found: {payload_data}", file=sys.stderr)
        return 2
    if not data_root.exists():
        print(f"ERROR: This does not look like the project root; missing: {data_root}", file=sys.stderr)
        return 2

    source_hash = directory_hash(payload_root)
    old_manifest = json_load(manifest_path, None)
    if old_manifest and old_manifest.get("status") == "applied" and old_manifest.get("source_hash") == source_hash:
        print("ELORA26 import is already recorded as successfully applied.")
        print(f"Manifest: {manifest_path}")
        print("No changes were made.")
        return 0

    existing_users = json_load(users_path, [])
    imported_users = json_load(payload_data / "users.json", [])
    existing_classes = json_load(classes_path, [])
    imported_classes = json_load(payload_data / "classes.json", [])
    legacy_mapping = json_load(payload_root / "import_mapping.json", [])

    if not isinstance(existing_users, list) or not isinstance(imported_users, list):
        raise ValueError("users.json must contain a JSON array")
    if not isinstance(existing_classes, list) or not isinstance(imported_classes, list):
        raise ValueError("classes.json must contain a JSON array")

    # ----- Plan user merge -------------------------------------------------
    occupied = {str(u.get("nickname", "")).casefold() for u in existing_users if u.get("nickname")}
    existing_by_name = {str(u.get("nickname", "")).casefold(): u for u in existing_users if u.get("nickname")}
    student_map: dict[str, str] = {}
    user_actions: list[dict[str, str]] = []
    users_after = copy.deepcopy(existing_users)

    for user in imported_users:
        old = str(user["nickname"])
        key = old.casefold()
        existing = existing_by_name.get(key)
        if existing is None:
            target = old
            action = "add"
            users_after.append(copy.deepcopy(user))
            existing_by_name[target.casefold()] = users_after[-1]
            occupied.add(target.casefold())
        elif (
            str(existing.get("class", "")) == str(user.get("class", ""))
            and str(existing.get("password", "")) == str(user.get("password", ""))
        ):
            # This looks like the same imported account was already created manually.
            target = str(existing["nickname"])
            action = "reuse-existing"
        else:
            target = unique_nickname(old, occupied)
            new_user = copy.deepcopy(user)
            new_user["nickname"] = target
            users_after.append(new_user)
            existing_by_name[target.casefold()] = new_user
            occupied.add(target.casefold())
            action = "rename-and-add"
        student_map[old] = target
        user_actions.append({"source": old, "target": target, "action": action})

    # ----- Plan class merge ------------------------------------------------
    classes_after = copy.deepcopy(existing_classes)
    existing_class_names = {str(c.get("class", "")) for c in existing_classes}
    class_actions: list[str] = []
    for cls in imported_classes:
        name = str(cls.get("class", ""))
        if name in existing_class_names:
            class_actions.append(f"preserve existing class {name}")
        else:
            classes_after.append(copy.deepcopy(cls))
            existing_class_names.add(name)
            class_actions.append(f"add class {name}")

    # ----- Plan student model merge ---------------------------------------
    student_plans: list[dict[str, Any]] = []
    for source in sorted((payload_data / "students").glob("*.json")):
        imported_model = json_load(source, {})
        old_id = str(imported_model.get("student_id") or source.stem)
        target_id = student_map.get(old_id, old_id)
        imported_model["student_id"] = target_id
        target = students_dir / f"{target_id}.json"
        if target.exists():
            existing_model = json_load(target, {})
            merged = merge_student_models(existing_model, imported_model, target_id)
            action = "merge"
        else:
            merged = imported_model
            action = "add"
        student_plans.append({"source": source, "target": target, "data": merged, "action": action})

    # ----- Plan session merge ---------------------------------------------
    session_plans: list[dict[str, Any]] = []
    reserved_session_ids: set[str] = set()
    for source in sorted((payload_data / "sessions" / "2026-05-30").glob("*.jsonl")):
        old_session_id = source.stem
        # First transform only student IDs; this is the preferred target content.
        preferred_bytes = transform_jsonl(source, student_map, None)
        target_session_id = old_session_id
        target = sessions_dir / f"{target_session_id}.jsonl"

        if target.exists():
            if target.read_bytes() == preferred_bytes:
                action = "skip-identical"
                content = preferred_bytes
            else:
                target_session_id = unique_session_id(old_session_id, sessions_dir, reserved_session_ids)
                target = sessions_dir / f"{target_session_id}.jsonl"
                content = transform_jsonl(source, student_map, target_session_id)
                action = "rename-and-add"
        else:
            content = preferred_bytes
            action = "add"

        reserved_session_ids.add(target_session_id)
        session_plans.append({
            "source": source,
            "source_session_id": old_session_id,
            "target": target,
            "target_session_id": target_session_id,
            "content": content,
            "action": action,
        })

    print("\nELORA26 SAFE MERGE PLAN")
    print("=" * 72)
    print(f"Project:            {project_root}")
    print(f"Source hash:        {source_hash[:16]}...")
    print(f"Imported users:     {len(imported_users)}")
    print(f"Imported sessions:  {len(session_plans)}")
    print(f"Imported students:  {len(student_plans)}")
    print("\nUsers:")
    counts: dict[str, int] = {}
    for a in user_actions:
        counts[a["action"]] = counts.get(a["action"], 0) + 1
    for action, count in sorted(counts.items()):
        print(f"  {action:20s} {count}")
    renamed = [a for a in user_actions if a["source"] != a["target"]]
    if renamed:
        print("  Conflict renames:")
        for a in renamed:
            print(f"    {a['source']} -> {a['target']}")

    print("\nClasses:")
    for action in class_actions:
        print(f"  {action}")

    session_counts: dict[str, int] = {}
    for p in session_plans:
        session_counts[p["action"]] = session_counts.get(p["action"], 0) + 1
    print("\nSessions:")
    for action, count in sorted(session_counts.items()):
        print(f"  {action:20s} {count}")

    student_counts: dict[str, int] = {}
    for p in student_plans:
        student_counts[p["action"]] = student_counts.get(p["action"], 0) + 1
    print("\nStudent models:")
    for action, count in sorted(student_counts.items()):
        print(f"  {action:20s} {count}")

    if not args.apply:
        print("\nDRY RUN ONLY - no files were changed.")
        print("If the plan looks correct, run:")
        print("  python scripts/merge_elora26_import.py --apply")
        return 0

    # ----- Apply -----------------------------------------------------------
    now = datetime.now(timezone.utc)
    backup_stamp = now.strftime("%Y%m%dT%H%M%SZ")
    backup_root = data_root / "backups" / f"{IMPORT_ID}_{backup_stamp}"
    backup_root.mkdir(parents=True, exist_ok=False)

    # Back up every existing file that may be modified.
    backup_file(users_path, project_root, backup_root)
    backup_file(classes_path, project_root, backup_root)
    backup_file(manifest_path, project_root, backup_root)
    for p in student_plans:
        if p["target"].exists() and p["action"] == "merge":
            backup_file(p["target"], project_root, backup_root)

    # Write the merged structured files atomically.
    atomic_json_write(users_path, users_after)
    atomic_json_write(classes_path, classes_after)

    students_dir.mkdir(parents=True, exist_ok=True)
    for p in student_plans:
        atomic_json_write(p["target"], p["data"])

    sessions_dir.mkdir(parents=True, exist_ok=True)
    for p in session_plans:
        if p["action"] == "skip-identical":
            continue
        # Refuse overwrite even if the filesystem changed after the dry-run/plan.
        try:
            with p["target"].open("xb") as f:
                f.write(p["content"])
                f.flush()
                os.fsync(f.fileno())
        except FileExistsError as exc:
            raise RuntimeError(f"Session target unexpectedly appeared during import: {p['target']}") from exc

    imports_state_dir.mkdir(parents=True, exist_ok=True)
    legacy_by_nickname = {str(x.get("nickname")): x for x in legacy_mapping}
    final_user_mapping = []
    for a in user_actions:
        row = copy.deepcopy(legacy_by_nickname.get(a["source"], {}))
        row.update({"source_nickname": a["source"], "target_nickname": a["target"], "merge_action": a["action"]})
        final_user_mapping.append(row)

    manifest = {
        "import_id": IMPORT_ID,
        "status": "applied",
        "applied_at": now.isoformat(),
        "source_hash": source_hash,
        "source_description": "Historical Elora26.json conversion; timestamps and classifications are reconstructed.",
        "backup_directory": str(backup_root.relative_to(project_root)),
        "user_mapping": final_user_mapping,
        "session_mapping": [
            {
                "source_session_id": p["source_session_id"],
                "target_session_id": p["target_session_id"],
                "action": p["action"],
            }
            for p in session_plans
        ],
        "counts": {
            "users_source": len(imported_users),
            "sessions_source": len(session_plans),
            "student_models_source": len(student_plans),
        },
    }
    atomic_json_write(manifest_path, manifest)

    print("\nMERGE COMPLETED SUCCESSFULLY")
    print(f"Backup:   {backup_root}")
    print(f"Manifest: {manifest_path}")
    print("The original import payload remains under imports/elora26_2026-05-30/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
