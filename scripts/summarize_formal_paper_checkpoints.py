#!/usr/bin/env python3
"""Summarize formal checkpoint scores and rank them against paper Table 2."""

import argparse
import glob
import json
import math
from pathlib import Path


PAPER_TARGETS = {
    "java": {
        "pass1_percent": 23.19,
        "pass10_percent": 40.30,
        "fsp": 6.76,
        "cer_percent": 3.12,
        "expected_problems": 67,
    },
    "sufu": {
        "pass1_percent": 43.10,
        "pass10_percent": 50.00,
        "fsp": 5.03,
        "cer_percent": 0.00,
        "expected_problems": 58,
    },
}


def checkpoint_sort_key(name):
    if name.startswith("epoch") and name[5:].isdigit():
        return (0, int(name[5:]))
    if name == "final":
        return (1, 0)
    return (2, name)


def score_row(path, branch, scope):
    raw = json.loads(path.read_text())
    pass_key = f"pass{int(raw.get('pass_at_k', 0))}"
    if pass_key != "pass10" or pass_key not in raw:
        raise ValueError(f"{path}: expected a pass@10 score artifact")
    problems = int(raw["problems"])
    if scope == "full" and problems != PAPER_TARGETS[branch]["expected_problems"]:
        raise ValueError(
            f"{path}: full score has {problems} problems, expected "
            f"{PAPER_TARGETS[branch]['expected_problems']}"
        )
    checkpoint = str(raw.get("model_type") or "")
    if not checkpoint:
        raise ValueError(f"{path}: missing model_type checkpoint identity")
    observed = {
        "pass1_percent": 100.0 * float(raw["pass1"]),
        "pass10_percent": 100.0 * float(raw["pass10"]),
        "fsp": float(raw["average_first_success_position"]),
        "cer_percent": 100.0 * float(raw["compile_error_rate"]),
    }
    target = PAPER_TARGETS[branch]
    deltas = {
        key: observed[key] - float(target[key])
        for key in ("pass1_percent", "pass10_percent", "fsp", "cer_percent")
    }
    distance = math.sqrt(sum(value * value for value in deltas.values()))
    return {
        "checkpoint": checkpoint,
        "scope": scope,
        "score_artifact": str(path),
        "checkpoint_path": raw.get("model_checkpoint_path", ""),
        "checkpoint_sha256": raw.get("model_checkpoint_sha256", ""),
        "problems": problems,
        "pass1_solved": len(raw.get("top1_solved", [])),
        "pass10_solved": len(raw.get("solved", [])),
        **observed,
        "paper_deltas": deltas,
        "paper_l2_distance": distance,
        "missing": int(raw.get("missing", 0)),
        "timeouts": int(raw.get("timeouts", 0)),
        "compile_errors": int(raw.get("compile_errors", 0)),
        "total_tested": int(raw.get("total_tested", 0)),
    }


def render_markdown(summary):
    target = summary["paper_target"]
    lines = [
        f"# {summary['branch'].title()} formal checkpoint comparison",
        "",
        "Paper target: "
        f"Pass@1 {target['pass1_percent']:.2f}%, "
        f"Pass@10 {target['pass10_percent']:.2f}%, "
        f"FSP {target['fsp']:.2f}, CER {target['cer_percent']:.2f}%.",
        "",
    ]
    if summary["branch"] == "java":
        lines.extend(
            [
                "Java paper warning: 23.19% is not attainable on 67 problems; "
                "it equals 16/69, whereas this repository test contains 67 rows. "
                "Always use the integer solved counts below.",
                "",
            ]
        )
    lines.extend(
        [
            "The L2 distance uses equal columns: Pass@1 percentage points, "
            "Pass@10 percentage points, FSP, and CER percentage points.",
            "",
            "| Scope | Checkpoint | Solved @1/@10 | Pass@1 | Pass@10 | FSP | CER | Paper L2 | Missing | Timeouts |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in summary["rows"]:
        lines.append(
            f"| {row['scope']} | `{row['checkpoint']}` | "
            f"{row['pass1_solved']}/{row['pass10_solved']} | "
            f"{row['pass1_percent']:.2f}% | {row['pass10_percent']:.2f}% | "
            f"{row['fsp']:.2f} | {row['cer_percent']:.2f}% | "
            f"{row['paper_l2_distance']:.3f} | {row['missing']} | {row['timeouts']} |"
        )
    lines.extend(
        [
            "",
            f"Closest full-test checkpoint: `{summary['closest_full_checkpoint']}`.",
            "",
            "Checkpoint selection uses full-test rows only. Non-overlap rows are "
            "reported as a separate generalization diagnostic and are not used "
            "to select the paper-matching checkpoint.",
            "",
            "The full frozen test is descriptive when exact test rows are present "
            "in training; it is not an independent held-out estimate.",
            "",
        ]
    )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--branch", choices=["java", "sufu"], required=True)
    parser.add_argument("--full_glob", action="append", required=True)
    parser.add_argument("--nonoverlap_glob", action="append", default=[])
    parser.add_argument("--json_out", type=Path, required=True)
    parser.add_argument("--markdown_out", type=Path, required=True)
    args = parser.parse_args()

    paths_by_scope = {"full": [], "nonoverlap": []}
    for scope, patterns in (
        ("full", args.full_glob),
        ("nonoverlap", args.nonoverlap_glob),
    ):
        for pattern in patterns:
            paths_by_scope[scope].extend(Path(path) for path in glob.glob(pattern))
        paths_by_scope[scope] = sorted(set(paths_by_scope[scope]))
    if not paths_by_scope["full"]:
        raise SystemExit("no full-test score artifacts matched")

    rows = []
    seen = set()
    for scope in ("full", "nonoverlap"):
        for path in paths_by_scope[scope]:
            row = score_row(path, args.branch, scope)
            identity = (scope, row["checkpoint"])
            if identity in seen:
                raise SystemExit(f"duplicate score for {identity}: {path}")
            seen.add(identity)
            rows.append(row)
    rows.sort(key=lambda row: (row["scope"] != "full", checkpoint_sort_key(row["checkpoint"])))
    full_rows = [row for row in rows if row["scope"] == "full"]
    closest_full = min(full_rows, key=lambda row: row["paper_l2_distance"])
    summary = {
        "branch": args.branch,
        "selection_policy": (
            "equal-column L2 distance on full frozen-test Pass@1 percentage "
            "points, Pass@10 percentage points, FSP, and CER percentage points"
        ),
        "paper_target": PAPER_TARGETS[args.branch],
        "java_pass1_denominator_warning": (
            args.branch == "java"
            and abs(PAPER_TARGETS["java"]["pass1_percent"] - 100 * 16 / 69) < 0.01
        ),
        "closest_full_checkpoint": closest_full["checkpoint"],
        "closest_full_artifact": closest_full["score_artifact"],
        "checkpoint_selection_scope": "full",
        "rows": rows,
    }
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    args.markdown_out.write_text(render_markdown(summary) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
