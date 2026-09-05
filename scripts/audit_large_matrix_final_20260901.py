#!/usr/bin/env python3
"""Audit all larger decoder-only score files without hiding interface failures."""

from __future__ import annotations

import json
from pathlib import Path

from validate_large_decoder_matrix_20260901 import ART, EXPECTED, MATRICES


def main() -> int:
    bad = False
    for slug, mapping in MATRICES.items():
        if slug not in {
            "qwen35_9b",
            "qwen35_27b",
            "qwen35_35b",
            "qwen36_27b",
            "qwen36_35b_a3b",
            "qwen38_27b",
            "qwen3_14b_base",
            "qwen3_30b_a3b_base",
            "qwen3_32b",
            "olmo3_1125_32b",
        }:
            continue
        failures: list[str] = []
        for condition, filename in mapping.items():
            benchmark = condition.rsplit("_", 1)[0]
            path = ART / filename
            if not path.is_file():
                failures.append(f"{condition}:missing_file")
                bad = True
                continue
            data = json.loads(path.read_text())
            expected = EXPECTED[benchmark]
            tested = data.get("total_tested")
            ignored = data.get("ignored", 0) or 0
            # ``total_tested`` excludes parser/interface markers.  Those
            # markers are still generated candidates and are reported below,
            # so accept tested+ignored when it covers the frozen denominator.
            covered = tested + ignored if isinstance(tested, int) else None
            if covered != expected or data.get("problems") not in (None, expected):
                failures.append(f"{condition}:covered={covered}/{expected}")
                bad = True
            for key in ("missing", "missing_problem_outputs"):
                if data.get(key, 0) not in (0, None):
                    failures.append(f"{condition}:{key}={data[key]}")
                    bad = True
        note = []
        for condition, filename in mapping.items():
            path = ART / filename
            if not path.is_file():
                continue
            data = json.loads(path.read_text())
            if data.get("ignored", 0):
                note.append(f"{condition}:ignored={data['ignored']}")
            if data.get("timeouts", 0):
                note.append(f"{condition}:timeouts={data['timeouts']}")
        if failures:
            print(f"INCOMPLETE {slug}: " + "; ".join(failures))
        elif note:
            print(f"COMPLETE_WITH_FAILURES {slug}: " + ", ".join(note))
        else:
            print(f"COMPLETE {slug}: 8/8")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
