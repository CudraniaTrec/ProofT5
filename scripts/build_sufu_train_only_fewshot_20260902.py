#!/usr/bin/env python3
"""Create a leakage-safe SuFu few-shot source from the mixed legacy file.

The legacy artifact contains train rows plus external synthetic rows and a
debug-overlap block copied from the test split.  Keep only rows explicitly
marked as the original training split and strip fields that are not needed to
compose a demonstration.  The source file is written additively so the old
artifact remains frozen and auditable.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


# Three legacy training rows are known to fail the SuFu type checker.  Keep
# them out of the reusable source so accidental first-k selection cannot
# surface an invalid demonstration.
INVALID_LEGACY_IDS = {
    "incre-tests-synduce-ptree-maxsum",
    "incre-tests-synduce-ptree-maxlast",
    "incre-tests-synduce-ptree-mul",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    rows = json.loads(args.source.read_text())
    kept = []
    for row in rows:
        if row.get("original_split") != "train":
            continue
        if row.get("debug_overlap"):
            continue
        if row.get("task_id") in INVALID_LEGACY_IDS:
            continue
        # Demonstrations need only the task id, public prompt, and complete
        # source.  Never carry tests, outputs, or debug metadata forward.
        kept.append(
            {
                "task_id": row["task_id"],
                "prompt": row["prompt"],
                "code": row["code"],
                "type": row.get("type", "train"),
                "benchmark": row.get("benchmark", "sufu_original"),
                "original_split": "train",
            }
        )

    if not kept:
        raise SystemExit("no explicit training rows found")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(kept, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {len(kept)} train-only rows to {args.output}")


if __name__ == "__main__":
    main()
