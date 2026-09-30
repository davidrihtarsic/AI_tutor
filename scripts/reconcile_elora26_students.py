#!/usr/bin/env python3
"""
Safely reconcile the historical ELORA26 import to the official student roster.

Default mode is DRY-RUN. Use --apply to make changes.

The script only acts on sessions that were created by the ELORA26 import
manifest. It does not rewrite unrelated classroom sessions.

Important design decision:
- Multiple historical logins remain separate JSONL session files.
- Their student_id is rewritten to the same canonical student identity.
This mirrors normal application behaviour: one student can have many sessions.
"""

from __future__ import annotations

import argparse
import copy
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


IMPORT_ID = "elora26_2026-05-30"


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return copy.deepcopy(default)
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json_atomic(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    tmp.replace(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    out = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def write_jsonl_atomic(path: Path, events: list[dict[str, Any]]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for event in events:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    tmp.replace(path)


def unique_nickname(preferred: str, occupied: set[str]) -> str:
    if preferred.casefold() not in occupied:
        return preferred
    candidate = preferred + "_elora26"
    i = 2
    while candidate.casefold() in occupied:
        candidate = f"{preferred}_elora26_{i}"
        i += 1
    return candidate


def _normalize_v3_topic(entry: dict[str, Any]) -> dict[str, Any]:
    """Normalize a topic record to Learner Model v3."""
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


def merge_topic_entry(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """Merge two Learner Model v3 topic records using evidence weights."""
    left = _normalize_v3_topic(a)
    right = _normalize_v3_topic(b)

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

def merge_student_models(models: list[dict[str, Any]], target_id: str) -> dict[str, Any]:
    result: dict[str, Any] = {"student_id": target_id, "tutors": {}}
    latest_updated = ""
    for model in models:
        latest_updated = max(latest_updated, str(model.get("updated_at", "")))
        for tutor_id, tutor_data in model.get("tutors", {}).items():
            target_tutor = result["tutors"].setdefault(tutor_id, {"topics": {}})
            for topic, entry in tutor_data.get("topics", {}).items():
                topics = target_tutor.setdefault("topics", {})
                if topic in topics:
                    topics[topic] = merge_topic_entry(topics[topic], entry)
                else:
                    topics[topic] = copy.deepcopy(entry)
    result["updated_at"] = latest_updated or datetime.now(timezone.utc).isoformat()
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Apply changes. Without this flag, only show the plan.")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    data_dir = project_root / "data"
    users_path = data_dir / "users.json"
    students_dir = data_dir / "students"
    sessions_dir = data_dir / "sessions" / "2026-05-30"
    manifest_path = data_dir / "imports" / f"{IMPORT_ID}.json"

    source_dir = project_root / "imports" / IMPORT_ID
    source_mapping_path = source_dir / "import_mapping.json"
    reconcile_path = source_dir / "student_reconciliation.json"

    manifest = load_json(manifest_path)
    if not manifest or manifest.get("status") != "applied":
        raise SystemExit(
            f"ELORA26 import manifest not found/applied: {manifest_path}\n"
            "Run the original ELORA26 merge first."
        )

    legacy_rows = load_json(source_mapping_path, [])
    reconciliation = load_json(reconcile_path, {})
    users = load_json(users_path, [])

    legacy_by_id = {str(r["legacy_id"]): r for r in legacy_rows}
    manifest_by_source = {
        str(r.get("source_nickname")): r
        for r in manifest.get("user_mapping", [])
    }

    # legacy_id -> live nickname produced by the original safe merge
    live_by_legacy: dict[str, str] = {}
    action_by_live: dict[str, str] = {}
    for legacy_id, row in legacy_by_id.items():
        source_nick = str(row["nickname"])
        m = manifest_by_source.get(source_nick)
        if not m:
            raise SystemExit(f"Manifest has no mapping for imported nickname {source_nick!r}")
        live_nick = str(m["target_nickname"])
        live_by_legacy[legacy_id] = live_nick
        action_by_live[live_nick] = str(m.get("merge_action", ""))

    existing_by_case = {str(u.get("nickname", "")).casefold(): u for u in users}
    occupied = set(existing_by_case)

    # Decide canonical live nickname for each official student.
    canonical_for_group: dict[str, str] = {}
    legacy_to_canonical: dict[str, str] = {}
    group_info: dict[str, dict[str, Any]] = {}

    for group in reconciliation.get("students", []):
        preferred = str(group["canonical_nickname"])
        anchor = group.get("anchor_legacy_id")

        if anchor and str(anchor) in live_by_legacy:
            canonical = live_by_legacy[str(anchor)]
        else:
            # Jure has no named anchor in the legacy export.
            current = existing_by_case.get(preferred.casefold())
            if current and str(current.get("class", "")) == "ELORA26":
                canonical = str(current["nickname"])
            else:
                canonical = unique_nickname(preferred, occupied)
                occupied.add(canonical.casefold())

        canonical_for_group[preferred] = canonical
        group_info[preferred] = group
        for legacy_id in group["legacy_ids"]:
            legacy_to_canonical[str(legacy_id)] = canonical

    # Map imported source session_id to final live session_id.
    session_target_by_source = {
        str(x["source_session_id"]): str(x["target_session_id"])
        for x in manifest.get("session_mapping", [])
    }

    # Find each legacy source session through its source nickname/session file.
    # The converted payload has one session file for each legacy thread.
    source_session_by_legacy: dict[str, str] = {}
    for src in (source_dir / "data" / "sessions" / "2026-05-30").glob("*.jsonl"):
        events = read_jsonl(src)
        if not events:
            continue
        src_student = str(events[0].get("student_id", ""))
        candidates = [
            legacy_id for legacy_id, row in legacy_by_id.items()
            if str(row.get("nickname")) == src_student
        ]
        if len(candidates) == 1:
            source_session_by_legacy[candidates[0]] = src.stem

    # Build exact set of live imported session files affected.
    session_plan: list[dict[str, Any]] = []
    imported_live_session_ids: set[str] = set()

    for legacy_id, source_session_id in source_session_by_legacy.items():
        target_session_id = session_target_by_source.get(source_session_id, source_session_id)
        imported_live_session_ids.add(target_session_id)

        if legacy_id == "345345":
            session_plan.append({
                "legacy_id": legacy_id,
                "target_session_id": target_session_id,
                "old_student": live_by_legacy[legacy_id],
                "new_student": None,
                "action": "archive-teacher-session",
            })
            continue

        canonical = legacy_to_canonical.get(legacy_id)
        if canonical:
            session_plan.append({
                "legacy_id": legacy_id,
                "target_session_id": target_session_id,
                "old_student": live_by_legacy[legacy_id],
                "new_student": canonical,
                "action": "rewrite-student-id" if live_by_legacy[legacy_id] != canonical else "keep",
            })

    # Detect any NON-import sessions that use aliases we would otherwise remove.
    all_aliases = set(live_by_legacy.values())
    aliases_with_external_sessions: set[str] = set()
    all_session_files = list((data_dir / "sessions").glob("*/*.jsonl"))
    for path in all_session_files:
        if path.parent.name == "2026-05-30" and path.stem in imported_live_session_ids:
            continue
        try:
            events = read_jsonl(path)
        except Exception:
            continue
        seen = {str(e.get("student_id", "")) for e in events}
        aliases_with_external_sessions |= (seen & all_aliases)

    # User plan: remove only accounts that were actually created by the historical importer.
    aliases_to_remove: set[str] = set()
    teacher_live = live_by_legacy.get("345345")
    for legacy_id, live_nick in live_by_legacy.items():
        canonical = legacy_to_canonical.get(legacy_id)
        created_by_import = action_by_live.get(live_nick) in {"add", "rename-and-add"}
        if legacy_id == "345345":
            if created_by_import and live_nick not in aliases_with_external_sessions:
                aliases_to_remove.add(live_nick)
            continue
        if canonical and live_nick != canonical and created_by_import and live_nick not in aliases_with_external_sessions:
            aliases_to_remove.add(live_nick)

    users_after = [
        copy.deepcopy(u) for u in users
        if str(u.get("nickname", "")) not in aliases_to_remove
    ]

    # Ensure Jure (or another anchorless canonical identity) exists.
    user_names_after = {str(u.get("nickname", "")).casefold() for u in users_after}
    for preferred, canonical in canonical_for_group.items():
        if canonical.casefold() not in user_names_after:
            users_after.append({
                "nickname": canonical,
                "password": f"elora-{preferred}",
                "class": "ELORA26",
                "enabled": True,
            })
            user_names_after.add(canonical.casefold())

    # Student model plan.
    models_by_canonical: dict[str, list[dict[str, Any]]] = {}
    alias_model_paths: dict[str, Path] = {}
    for group in reconciliation.get("students", []):
        canonical = canonical_for_group[str(group["canonical_nickname"])]
        models_by_canonical.setdefault(canonical, [])
        for legacy_id in group["legacy_ids"]:
            live_nick = live_by_legacy.get(str(legacy_id))
            if not live_nick:
                continue
            p = students_dir / f"{live_nick}.json"
            if p.exists():
                models_by_canonical[canonical].append(load_json(p, {}))
                alias_model_paths[live_nick] = p

    # Include canonical's current model once if it wasn't already included.
    for canonical, models in models_by_canonical.items():
        cp = students_dir / f"{canonical}.json"
        if cp.exists() and cp not in alias_model_paths.values():
            models.append(load_json(cp, {}))

    merged_models = {
        canonical: merge_student_models(models, canonical)
        for canonical, models in models_by_canonical.items()
        if models
    }

    print("\nELORA26 STUDENT RECONCILIATION - DRY RUN" if not args.apply else "\nELORA26 STUDENT RECONCILIATION - APPLY")
    print("=" * 72)
    for group in reconciliation.get("students", []):
        preferred = str(group["canonical_nickname"])
        canonical = canonical_for_group[preferred]
        print(f"{group['full_name']:<48} -> {canonical}")
        print(f"  official ID: {group['official_id']} | confidence: {group['confidence']}")
        print(f"  legacy IDs: {', '.join(group['legacy_ids'])}")
    print("\nTeacher/test user:")
    print(f"  David ({live_by_legacy.get('345345', 'not found')}) -> excluded from student analytics")

    print("\nSession changes:")
    changed = [p for p in session_plan if p["action"] != "keep"]
    print(f"  imported sessions found: {len(session_plan)}")
    print(f"  sessions to rewrite/archive: {len(changed)}")

    if aliases_with_external_sessions:
        print("\nSAFETY WARNING: these imported aliases also have non-import sessions.")
        print("Their accounts/models will NOT be deleted automatically:")
        for x in sorted(aliases_with_external_sessions):
            print(f"  - {x}")

    print(f"\nImported duplicate accounts to remove safely: {len(aliases_to_remove)}")
    for x in sorted(aliases_to_remove):
        print(f"  - {x}")

    print("\nImportant inference:")
    print("  Anonymous one-sensor line-following cluster -> Jure is LOW confidence.")
    print("  Edit imports/elora26_2026-05-30/student_reconciliation.json before --apply")
    print("  if you want a different attribution.")

    if not args.apply:
        print("\nNo files changed. Run with --apply when the plan is acceptable.")
        return 0

    # Backup
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = data_dir / "backups" / f"elora26_reconcile_{stamp}"
    backup.mkdir(parents=True, exist_ok=False)

    if users_path.exists():
        shutil.copy2(users_path, backup / "users.json")

    backup_students = backup / "students"
    backup_sessions = backup / "sessions"
    backup_students.mkdir()
    backup_sessions.mkdir()

    # Back up affected models
    for p in set(alias_model_paths.values()) | {students_dir / f"{c}.json" for c in merged_models}:
        if p.exists():
            shutil.copy2(p, backup_students / p.name)

    # Back up affected session files
    for plan in session_plan:
        p = sessions_dir / f"{plan['target_session_id']}.jsonl"
        if p.exists():
            shutil.copy2(p, backup_sessions / p.name)

    # Rewrite/archive sessions
    teacher_archive = data_dir / "imports" / "elora26_teacher_sessions"
    teacher_archive.mkdir(parents=True, exist_ok=True)

    for plan in session_plan:
        p = sessions_dir / f"{plan['target_session_id']}.jsonl"
        if not p.exists():
            continue
        if plan["action"] == "archive-teacher-session":
            dst = teacher_archive / p.name
            if dst.exists():
                dst = teacher_archive / f"{p.stem}_{stamp}.jsonl"
            shutil.move(str(p), str(dst))
            continue
        if plan["new_student"] and plan["old_student"] != plan["new_student"]:
            events = read_jsonl(p)
            for e in events:
                if str(e.get("student_id", "")) == plan["old_student"]:
                    e["student_id"] = plan["new_student"]
            write_jsonl_atomic(p, events)

    # Users
    write_json_atomic(users_path, users_after)

    # Models
    for canonical, model in merged_models.items():
        write_json_atomic(students_dir / f"{canonical}.json", model)

    for alias, p in alias_model_paths.items():
        # Remove only imported duplicate aliases that are safe to remove.
        if alias in aliases_to_remove and alias not in canonical_for_group.values() and p.exists():
            p.unlink()

    # Remove teacher model if importer-created and safe.
    if teacher_live and teacher_live in aliases_to_remove:
        tp = students_dir / f"{teacher_live}.json"
        if tp.exists():
            tp.unlink()

    result_manifest = {
        "reconciliation_id": "elora26_official_roster_v1",
        "applied_at": datetime.now(timezone.utc).isoformat(),
        "backup_directory": str(backup.relative_to(project_root)),
        "canonical_students": [
            {
                "official_id": g["official_id"],
                "full_name": g["full_name"],
                "canonical_nickname": canonical_for_group[g["canonical_nickname"]],
                "legacy_ids": g["legacy_ids"],
                "confidence": g["confidence"],
            }
            for g in reconciliation.get("students", [])
        ],
        "teacher_session_archived": True,
        "aliases_removed": sorted(aliases_to_remove),
        "external_session_aliases_preserved": sorted(aliases_with_external_sessions),
    }
    write_json_atomic(data_dir / "imports" / "elora26_student_reconciliation.json", result_manifest)

    print("\nRECONCILIATION COMPLETED")
    print(f"Backup: {backup}")
    print("Manifest: data/imports/elora26_student_reconciliation.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
