"""Command-line utility for synchronising tutor knowledge without the web UI.

Examples:
    python scripts/sync_vector_stores.py robotics
    python scripts/sync_vector_stores.py --all
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow the script to import project modules when launched from scripts/.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.tutor_service import discover_tutors  # noqa: E402
from services.vector_store_service import sync_tutor  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync tutor Markdown knowledge to OpenAI.")
    parser.add_argument("tutor_id", nargs="?", help="Tutor folder ID, e.g. robotics")
    parser.add_argument("--all", action="store_true", help="Synchronise all discovered tutors")
    args = parser.parse_args()

    if args.all:
        tutor_ids = [t["id"] for t in discover_tutors()]
    elif args.tutor_id:
        tutor_ids = [args.tutor_id]
    else:
        parser.error("Provide tutor_id or --all")

    for tutor_id in tutor_ids:
        print(f"\n=== {tutor_id} ===")
        result = sync_tutor(tutor_id)
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
