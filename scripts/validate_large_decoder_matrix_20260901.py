#!/usr/bin/env python3
"""Validate that each larger decoder-only row has a complete 4×(zero/F3) matrix.

The validator deliberately checks task totals and missing/timeout counts in the
score JSONs, rather than treating the presence of a file as evidence that an
evaluation finished.  It is read-only and is safe to run while matrices are
still being generated.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ART = Path("/data2/x/hzc/prooft5/artifacts/major_revision_decoder_only_multibenchmark_20260828")

EXPECTED = {
    "mbjp": 67,
    "he": 16,
    "gfg": 103,
    "sufu": 58,
}

MATRICES = {
    "qwen35_9b": {
        "mbjp_zero": "qwen35_9b_mbjp_zero_score.json",
        "mbjp_f3": "qwen35_9b_mbjp_syn3_score.json",
        "he_zero": "qwen35_9b_he_zero_full_score.json",
        "he_f3": "qwen35_9b_he_f3_full_score.json",
        "gfg_zero": "qwen35_9b_gfg_zero_full_score.json",
        "gfg_f3": "qwen35_9b_gfg_f3_full_p1_score.json",
        "sufu_zero": "qwen35_9b_sufu_zero_highinfo_score.json",
        "sufu_f3": "qwen35_9b_sufu_f3_highinfo_score.json",
    },
    "qwen35_27b": {f"{bench}_{shot}": f"qwen35_27b_{bench}_{shot}_score.json" for bench in EXPECTED for shot in ("zero", "f3")},
    "qwen35_35b": {f"{bench}_{shot}": f"qwen35_35b_{bench}_{shot}_score.json" for bench in EXPECTED for shot in ("zero", "f3")},
}

for slug in (
    "qwen36_27b",
    "qwen36_35b_a3b",
    "qwen38_27b",
    "qwen3_14b_base",
    "qwen3_30b_a3b_base",
    "qwen3_32b",
    "olmo3_1125_32b",
):
    MATRICES[slug] = {
        f"{bench}_{shot}": f"{slug}_{bench}_{shot}_score.json"
        for bench in EXPECTED
        for shot in ("zero", "f3")
    }


def validate(path: Path, benchmark: str) -> list[str]:
    if not path.is_file() or path.stat().st_size == 0:
        return ["missing_file"]
    try:
        data = json.loads(path.read_text())
    except Exception as exc:  # pragma: no cover - diagnostic branch
        return [f"invalid_json:{type(exc).__name__}"]
    errors: list[str] = []
    expected = EXPECTED[benchmark]
    if data.get("total_tested") != expected:
        errors.append(f"total={data.get('total_tested')} expected={expected}")
    if data.get("problems") not in (None, expected):
        errors.append(f"problems={data.get('problems')} expected={expected}")
    for key in ("missing", "missing_problem_outputs", "ignored", "timeouts"):
        value = data.get(key, 0)
        if value not in (0, None):
            errors.append(f"{key}={value}")
    solved = data.get("solved")
    if not isinstance(solved, list):
        errors.append("solved_not_list")
    elif len(solved) > expected:
        errors.append(f"solved={len(solved)}>{expected}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug", action="append", choices=sorted(MATRICES))
    args = parser.parse_args()
    slugs = args.slug or list(MATRICES)
    failed = False
    for slug in slugs:
        problems: list[str] = []
        for condition, filename in MATRICES[slug].items():
            benchmark = condition.rsplit("_", 1)[0]
            errors = validate(ART / filename, benchmark)
            if errors:
                problems.append(f"{condition}({','.join(errors)})")
        if problems:
            failed = True
            print(f"INCOMPLETE {slug}: " + "; ".join(problems))
        else:
            print(f"COMPLETE {slug}: 8/8")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
