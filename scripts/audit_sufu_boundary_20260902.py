#!/usr/bin/env python3
"""Audit additive 2026-09-02 SuFu boundary/train-only runs."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TASK = "sufu_original_test_t5gemma2_20260731"
OUT = ROOT / "Utils" / "output" / f"{TASK}_test_ans"
ART = ROOT / "artifacts" / "major_revision_decoder_only_multibenchmark_20260828"
FEWSHOT = ART / "inputs" / "sufu_few_shot_train_only_noio_notest_20260902.json"
SLUGS = ("codegemma", "gemma2", "starcoder2", "smollm3", "granite", "qwen3_4b", "mimo")


def main() -> int:
    failed = False
    if not FEWSHOT.is_file():
        print(f"INCOMPLETE few-shot source: {FEWSHOT}")
        return 1
    few_shot_rows = json.loads(FEWSHOT.read_text())
    if (
        not few_shot_rows
        or any(row.get("original_split") != "train" for row in few_shot_rows)
        or any(row.get("debug_overlap") for row in few_shot_rows)
    ):
        print("INVALID few-shot source: expected explicit train rows only")
        failed = True
    required_ids = {
        "incre-tests-synduce-constraints-sortedlist-parallel_max2",
        "incre-tests-synduce-zipper-list_sum",
        "incre-tests-synduce-constraints-all_positive-sndmax",
    }
    if not required_ids.issubset({row.get("task_id") for row in few_shot_rows}):
        print("INVALID few-shot source: required demonstration IDs are missing")
        failed = True
    for slug in SLUGS:
        for condition in ("zero", "f3"):
            # Zero-shot has no demonstrations and the complete boundary-only
            # rerun is already valid; only F3 needs the train-only replacement.
            suffix = "trainonly_valid_stopmain_20260902" if condition == "f3" else "boundary_20260902"
            tag = f"{slug}_sufu_{condition}_{suffix}"
            directory = OUT / tag
            candidates = sorted(directory.glob("*_0.txt")) if directory.is_dir() else []
            score_path = ART / f"{tag}_score.json"
            if len(candidates) != 58 or not score_path.is_file():
                print(f"INCOMPLETE {tag}: candidates={len(candidates)} score={score_path.is_file()}")
                failed = True
                continue
            manifest = json.loads((directory / "baseline_manifest.json").read_text())
            score = json.loads(score_path.read_text())
            args = manifest["arguments"]
            ids = args.get("few_shot_ids", "")
            ok = (
                args.get("few_shot_k") == (3 if condition == "f3" else 0)
                and args.get("hidden_tests_exposed") is False
                and args.get("max_tokens") == 2048
                and (condition != "f3" or "incre-tests-synduce-zipper-list_sum" in ids)
                and (condition != "f3" or "incre-tests-synduce-constraints-all_positive-sndmax" in ids)
                and score.get("problems") == 58
                and score.get("missing") == 0
            )
            if not ok:
                print(f"INVALID {tag}: manifest/score contract mismatch")
                failed = True
            print(
                f"{tag}: pass1={len(score.get('top1_solved', []))}/58 "
                f"compile={score.get('compile_errors')}/{score.get('total_tested')} "
                f"timeouts={score.get('timeouts')}"
            )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
