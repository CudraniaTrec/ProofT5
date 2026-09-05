#!/usr/bin/env python3
"""Audit the additive Qwen3-32B prefix-completion Java reruns."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts" / "major_revision_decoder_only_multibenchmark_20260828"

ROWS = {
    "mbjp_zero": (67, "qwen3_32b_prefix_mbjp_zero_20260902"),
    "mbjp_f3": (67, "qwen3_32b_prefix_mbjp_f3_20260902"),
    "he_zero": (16, "qwen3_32b_prefix_he_zero_20260902"),
    "he_f3": (16, "qwen3_32b_prefix_he_f3_20260902"),
    "gfg_zero": (103, "qwen3_32b_prefix_gfg_zero_20260902"),
    "gfg_f3": (103, "qwen3_32b_prefix_gfg_f3_20260902"),
}


def main() -> int:
    failed = False
    for label, (expected, tag) in ROWS.items():
        # The score JSON stores candidates under the benchmark-specific output
        # root; locate it from the manifest rather than hard-coding that root.
        matches = list((ROOT / "Utils" / "output").glob(f"**/{tag}/baseline_manifest.json"))
        score_path = ART / f"{tag}_score.json"
        errors: list[str] = []
        if len(matches) != 1:
            errors.append(f"manifest_matches={len(matches)}")
        if not score_path.is_file():
            errors.append("missing_score")
        if errors:
            failed = True
            print(f"INVALID {label}: " + ", ".join(errors))
            continue
        manifest_path = matches[0]
        manifest = json.loads(manifest_path.read_text())
        score = json.loads(score_path.read_text())
        args = manifest.get("arguments", {})
        candidates = sorted(manifest_path.parent.glob("*_0.txt"))
        if len(candidates) != expected:
            errors.append(f"candidates={len(candidates)}/{expected}")
        if args.get("completion_mode") != "prefix_completion":
            errors.append(f"completion_mode={args.get('completion_mode')}")
        want_k = 0 if label.endswith("zero") else 3
        if args.get("few_shot_k") != want_k:
            errors.append(f"few_shot_k={args.get('few_shot_k')}")
        if args.get("hidden_tests_exposed") not in (None, False):
            errors.append("hidden_tests_exposed!=false")
        if score.get("total_tested") != expected:
            errors.append(f"total_tested={score.get('total_tested')}")
        for key in ("missing", "missing_problem_outputs", "ignored"):
            if score.get(key, 0) not in (0, None):
                errors.append(f"{key}={score.get(key)}")
        if errors:
            failed = True
            print(f"INVALID {label}: " + ", ".join(errors))
            continue
        solved = len(score.get("top1_solved", score.get("solved", [])))
        print(
            f"COMPLETE {label}: {solved}/{expected}; "
            f"compile={score.get('compile_errors', 0)}; "
            f"timeouts={score.get('timeouts', 0) or 0}"
        )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
