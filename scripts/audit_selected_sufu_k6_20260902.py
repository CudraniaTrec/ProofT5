#!/usr/bin/env python3
"""Audit the selected leakage-safe SuFu k=6 rows (read-only)."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts" / "major_revision_decoder_only_multibenchmark_20260828"
OUT = ROOT / "Utils" / "output" / "sufu_original_test_t5gemma2_20260731_test_ans"

TAGS = (
    "sufu_mimo_canonical6_full_final_20260902",
    "sufu_q14b_balanced6_full_final_20260902",
    "sufu_q30b_canonical6_prefix_final_20260902",
    "sufu_q32b_canonical6_prefix_final_20260902",
    "sufu_q36_27b_canonical6_prefix_final_20260902",
)

SCORE_FILES = {
    "sufu_mimo_canonical6_full_final_20260902": "mimo_canonical6_full_final_20260902_score.json",
    "sufu_q14b_balanced6_full_final_20260902": "q14b_balanced6_full_final_20260902_score.json",
    "sufu_q30b_canonical6_prefix_final_20260902": "q30b_canonical6_prefix_full_final_20260902_score.json",
    "sufu_q32b_canonical6_prefix_final_20260902": "q32b_canonical6_prefix_full_final_20260902_score.json",
    "sufu_q36_27b_canonical6_prefix_final_20260902": "q36_27b_canonical6_prefix_full_final_20260902_score.json",
}


def main() -> int:
    failed = False
    for tag in TAGS:
        directory = OUT / tag
        score_path = ART / SCORE_FILES[tag]
        errors: list[str] = []
        candidates = sorted(directory.glob("*_0.txt")) if directory.is_dir() else []
        if len(candidates) != 58:
            errors.append(f"candidates={len(candidates)}/58")
        if not score_path.is_file():
            errors.append("missing_score")
        if not (directory / "baseline_manifest.json").is_file():
            errors.append("missing_manifest")
        if errors:
            failed = True
            print(f"INVALID {tag}: " + ", ".join(errors))
            continue

        manifest = json.loads((directory / "baseline_manifest.json").read_text())
        score = json.loads(score_path.read_text())
        args = manifest.get("arguments", {})
        ids = args.get("few_shot_example_ids", [])
        if args.get("few_shot_k") != 6:
            errors.append(f"few_shot_k={args.get('few_shot_k')}")
        if len(ids) != 6:
            errors.append(f"few_shot_ids={len(ids)}")
        if args.get("hidden_tests_exposed") is not False:
            errors.append("hidden_tests_exposed!=false")
        if "train_only" not in str(args.get("few_shot_dataset", "")):
            errors.append("non_train_only_source")
        if score.get("output_comparison") != "full_stdout":
            errors.append(f"comparison={score.get('output_comparison')}")
        if score.get("total_tested") != 58:
            errors.append(f"total_tested={score.get('total_tested')}")
        for key in ("missing", "missing_problem_outputs", "ignored"):
            if score.get(key, 0) not in (0, None):
                errors.append(f"{key}={score.get(key)}")
        if errors:
            failed = True
            print(f"INVALID {tag}: " + ", ".join(errors))
            continue
        solved = len(score.get("top1_solved", score.get("solved", [])))
        print(
            f"COMPLETE {tag}: {solved}/58; "
            f"compile={score.get('compile_errors', 0)}; "
            f"timeouts={score.get('timeouts', 0) or 0}; "
            f"ignored={score.get('ignored', 0) or 0}"
        )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
