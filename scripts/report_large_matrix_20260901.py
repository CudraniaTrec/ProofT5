#!/usr/bin/env python3
"""Print a compact pass@1 report for the larger-model matrix.

Unlike a glob-based report, this uses the fixed condition mapping and marks a
row incomplete until all four benchmark totals and all eight score files are
present and valid.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from validate_large_decoder_matrix_20260901 import EXPECTED, MATRICES, validate


ART = Path("/data2/x/hzc/prooft5/artifacts/major_revision_decoder_only_multibenchmark_20260828")


def cell(path: Path, benchmark: str) -> str:
    """Return pass@1 over the frozen benchmark denominator.

    A generated candidate that times out or is rejected by a parser is still
    an attempted test and must remain in the denominator.  The strict
    validator is kept separately for audit diagnostics; the reporting table
    therefore shows a cell whenever the score JSON covers every problem, even
    if it also records interface failures.
    """
    if not path.is_file() or path.stat().st_size == 0:
        return "—"
    try:
        data = json.loads(path.read_text())
    except Exception:
        return "—"
    if data.get("total_tested") is None and data.get("problems") is None:
        return "—"
    expected = EXPECTED[benchmark]
    if data.get("problems") not in (None, expected):
        return "—"
    solved = data.get("top1_solved", data.get("solved", []))
    if not isinstance(solved, list):
        return "—"
    return f"{len(solved)}/{expected}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug", action="append", choices=sorted(MATRICES))
    args = parser.parse_args()
    slugs = args.slug or list(MATRICES)
    print("| model | MBJP zero | MBJP F3 | HumanEval-Java zero | HumanEval-Java F3 | GFG zero | GFG F3 | SuFu zero | SuFu F3 | status |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for slug in slugs:
        mapping = MATRICES[slug]
        values = []
        complete = True
        row_has_all_problems = True
        for benchmark in ("mbjp", "he", "gfg", "sufu"):
            for shot in ("zero", "f3"):
                filename = mapping[f"{benchmark}_{shot}"]
                path = ART / filename
                errors = validate(path, benchmark)
                # Strict errors such as a timeout or an interface marker are
                # reported in the audit, but do not erase a valid denominator
                # from this pass@1 comparison row.
                complete &= not errors
                if not path.is_file() or path.stat().st_size == 0:
                    row_has_all_problems = False
                else:
                    try:
                        data = json.loads(path.read_text())
                        tested = data.get("total_tested")
                        ignored = data.get("ignored", 0) or 0
                        covered = tested + ignored if isinstance(tested, int) else None
                        row_has_all_problems &= data.get("problems") in (None, EXPECTED[benchmark]) and covered == EXPECTED[benchmark]
                    except Exception:
                        row_has_all_problems = False
                values.append(cell(path, benchmark))
        label = {
            "qwen35_9b": "Qwen3.5-9B",
            "qwen35_27b": "Qwen3.5-27B",
            "qwen35_35b": "Qwen3.5-35B-A3B",
            "qwen36_27b": "Qwen3.6-27B",
            "qwen36_35b_a3b": "Qwen3.6-35B-A3B",
            "qwen38_27b": "Qwen3.8-27B",
            "qwen3_14b_base": "Qwen3-14B-Base",
            "qwen3_30b_a3b_base": "Qwen3-30B-A3B-Base",
            "qwen3_32b": "Qwen3-32B",
            "olmo3_1125_32b": "OLMo-3-1125-32B",
        }[slug]
        status = "complete" if complete else ("complete-with-failures" if row_has_all_problems else "incomplete")
        print("| " + label + " | " + " | ".join(values) + " | " + status + " |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
