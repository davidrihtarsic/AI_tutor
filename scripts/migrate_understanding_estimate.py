#!/usr/bin/env python3
"""Migrate legacy learner-state topic records to learner model v2.

Default mode is dry-run. Use --apply to write changes.

The migration preserves the numeric value of the old ``support_estimate``
field because the legacy update rule already used larger values for stronger
demonstrated understanding. Since the old files do not retain the individual
positive/neutral/negative classifications, the script does not invent them.
Instead, existing observations are retained only as historical weight via
``legacy_evidence_observations``. New evidence counters start at zero.
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json_atomic(path: Path, payload: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    tmp.replace(path)


def migrate_topic(topic_state: dict[str, Any]) -> bool:
    """Migrate one topic record in place. Return True if it changed."""
    changed = False

    if "understanding_estimate" not in topic_state and "support_estimate" in topic_state:
        topic_state["understanding_estimate"] = float(topic_state.pop("support_estimate"))
        changed = True

    if "understanding_estimate" not in topic_state:
        topic_state["understanding_estimate"] = 0.5
        changed = True

    observations = int(topic_state.get("observations", 0) or 0)

    defaults = {
        "evidence_observations": 0,
        "positive_evidence": 0,
        "negative_evidence": 0,
        "legacy_evidence_observations": observations,
    }
    for key, value in defaults.items():
        if key not in topic_state:
            topic_state[key] = value
            changed = True

    if observations > 0 and "legacy_evidence" not in topic_state:
        topic_state["legacy_evidence"] = True
        changed = True

    return changed


def migrate_student_state(state: dict[str, Any]) -> int:
    """Migrate all topic records in one student state. Return changed topic count."""
    changed_topics = 0
    for course_state in state.get("courses", {}).values():
        for tutor_state in course_state.get("tutors", {}).values():
            for topic_state in tutor_state.get("topics", {}).values():
                if isinstance(topic_state, dict) and migrate_topic(topic_state):
                    changed_topics += 1
    return changed_topics


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write migrated files. Without this flag the script only reports changes.",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    students_dir = project_root / "data" / "students"

    if not students_dir.exists():
        raise SystemExit(f"Student state directory does not exist: {students_dir}")

    files = sorted(students_dir.glob("*.json"))
    changed_files: list[tuple[Path, dict[str, Any], int]] = []
    changed_topics = 0

    for path in files:
        state = load_json(path)
        count = migrate_student_state(state)
        if count:
            changed_files.append((path, state, count))
            changed_topics += count

    print(f"Student files scanned: {len(files)}")
    print(f"Student files to change: {len(changed_files)}")
    print(f"Topic records to change: {changed_topics}")

    if not args.apply:
        print("\nDRY-RUN: no files changed.")
        print("Run again with --apply when the report looks correct.")
        return 0

    if not changed_files:
        print("\nNothing to migrate.")
        return 0

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = project_root / "data" / "backups" / f"learner_model_v2_{stamp}"
    backup_students = backup_dir / "students"
    backup_students.mkdir(parents=True, exist_ok=False)

    for path, state, _ in changed_files:
        shutil.copy2(path, backup_students / path.name)
        write_json_atomic(path, state)

    print("\nMigration completed.")
    print(f"Backup: {backup_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
