#!/usr/bin/env python3
"""Validate and summarize the six clean Java reproduction score artifacts."""

import argparse
import json
import math
from pathlib import Path


EXPECTED = {"mbjp": 67, "humaneval": 66}
PAPER = {
    ("mbjp", "plain"): (17.91, 35.82),
    ("mbjp", "coqview"): (23.19, 40.30),
}


def wilson(successes, total, z=1.959963984540054):
    if total <= 0:
        raise ValueError("Wilson interval requires a positive denominator")
    p = successes / total
    scale = 1.0 + z * z / total
    center = (p + z * z / (2.0 * total)) / scale
    radius = (
        z
        * math.sqrt(p * (1.0 - p) / total + z * z / (4.0 * total * total))
        / scale
    )
    return 100.0 * (center - radius), 100.0 * (center + radius)


def load_score(path, benchmark, model):
    raw = json.loads(path.read_text())
    required = {
        "pass_at_k",
        "pass1",
        "pass10",
        "problems",
        "top1_solved",
        "solved",
        "missing_problem_outputs",
        "model_checkpoint_path",
        "model_checkpoint_sha256",
    }
    missing = sorted(required - raw.keys())
    if missing:
        raise ValueError(f"{path}: missing required fields {missing}")
    if int(raw["pass_at_k"]) != 10:
        raise ValueError(f"{path}: pass_at_k is not 10")
    total = int(raw["problems"])
    if total != EXPECTED[benchmark]:
        raise ValueError(
            f"{path}: {benchmark} denominator {total} != {EXPECTED[benchmark]}"
        )
    if int(raw["missing_problem_outputs"]) != 0:
        raise ValueError(f"{path}: contains missing problem outputs")
    checkpoint_path = str(raw["model_checkpoint_path"] or "")
    checkpoint_sha = str(raw["model_checkpoint_sha256"] or "")
    if not checkpoint_path or len(checkpoint_sha) != 64:
        raise ValueError(f"{path}: incomplete checkpoint provenance")

    pass1_count = len(raw["top1_solved"])
    pass10_count = len(raw["solved"])
    if pass1_count > pass10_count or pass10_count > total:
        raise ValueError(f"{path}: invalid solved-count ordering")
    pass1 = pass1_count / total
    pass10 = pass10_count / total
    if not math.isclose(float(raw["pass1"]), pass1, abs_tol=1e-12):
        raise ValueError(f"{path}: pass1 disagrees with top1_solved")
    if not math.isclose(float(raw["pass10"]), pass10, abs_tol=1e-12):
        raise ValueError(f"{path}: pass10 disagrees with solved")

    p1_ci = wilson(pass1_count, total)
    p10_ci = wilson(pass10_count, total)
    return {
        "benchmark": benchmark,
        "model": model,
        "score_artifact": str(path),
        "checkpoint_path": checkpoint_path,
        "checkpoint_sha256": checkpoint_sha,
        "problems": total,
        "pass1_count": pass1_count,
        "pass10_count": pass10_count,
        "pass1_percent": 100.0 * pass1,
        "pass10_percent": 100.0 * pass10,
        "pass1_wilson95": list(p1_ci),
        "pass10_wilson95": list(p10_ci),
        "compile_error_rate": raw.get("compile_error_rate"),
        "timeouts": int(raw.get("timeouts", 0)),
    }


def render_markdown(summary):
    selection = summary["checkpoint_selection"]
    lines = [
        "# Clean Java T5Gemma2 reproduction",
        "",
        "All reproduced rows use disjoint training/test data and one frozen "
        "checkpoint per model. Intervals are 95% Wilson binomial intervals over "
        "problems.",
        "",
        "The plain-model checkpoint is selected without validation or test scores: "
        f"{selection['plain']}. Coq-only and CoqView use their prespecified final "
        "checkpoints.",
        "",
        "| Benchmark | Model | pass@1 | 95% CI | pass@10 | 95% CI |",
        "|---|---|---:|---:|---:|---:|",
    ]
    label = {"plain": "T5Gemma2-2B", "coq": "Coq-only", "coqview": "CoqView"}
    bench = {"mbjp": "Java / MBJP", "humaneval": "HumanEval Java"}
    for row in summary["rows"]:
        p1_lo, p1_hi = row["pass1_wilson95"]
        p10_lo, p10_hi = row["pass10_wilson95"]
        lines.append(
            f"| {bench[row['benchmark']]} | {label[row['model']]} | "
            f"{row['pass1_percent']:.2f}% ({row['pass1_count']}/{row['problems']}) | "
            f"[{p1_lo:.2f}, {p1_hi:.2f}] | "
            f"{row['pass10_percent']:.2f}% ({row['pass10_count']}/{row['problems']}) | "
            f"[{p10_lo:.2f}, {p10_hi:.2f}] |"
        )
    lines.extend(
        [
            "",
            "## Paper comparison",
            "",
            "| Benchmark | Model | Paper pass@1 | Paper pass@10 | Reproduced delta @1/@10 |",
            "|---|---|---:|---:|---:|",
        ]
    )
    rows = {(row["benchmark"], row["model"]): row for row in summary["rows"]}
    for key, (paper1, paper10) in PAPER.items():
        row = rows[key]
        lines.append(
            f"| Java / MBJP | {label[key[1]]} | {paper1:.2f}% | {paper10:.2f}% | "
            f"{row['pass1_percent'] - paper1:+.2f} / "
            f"{row['pass10_percent'] - paper10:+.2f} pp |"
        )
    lines.extend(
        [
            "",
            "The paper does not report a T5Gemma2 Coq-only row or HumanEval Java "
            "rows. Its Java CoqView pass@1 value (23.19%) is not attainable as an "
            "integer count over 67 problems; 16/67 is 23.88%.",
            "",
        ]
    )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    for benchmark in EXPECTED:
        for model in ("plain", "coq", "coqview"):
            parser.add_argument(
                f"--{benchmark}_{model}", type=Path, required=True
            )
    parser.add_argument("--json_out", type=Path, required=True)
    parser.add_argument("--markdown_out", type=Path, required=True)
    parser.add_argument(
        "--plain_checkpoint_selection",
        required=True,
        help="Test-independent rule used to select the plain-model checkpoint",
    )
    parser.add_argument(
        "--plain_selection_evidence", type=Path, required=True
    )
    args = parser.parse_args()

    rows = []
    for benchmark in ("mbjp", "humaneval"):
        for model in ("plain", "coq", "coqview"):
            path = getattr(args, f"{benchmark}_{model}")
            rows.append(load_score(path, benchmark, model))
    checkpoint_by_model = {}
    for model in ("plain", "coq", "coqview"):
        identities = {
            (row["checkpoint_path"], row["checkpoint_sha256"])
            for row in rows
            if row["model"] == model
        }
        if len(identities) != 1:
            raise ValueError(
                f"{model}: MBJP and HumanEval do not use one identical checkpoint"
            )
        checkpoint_by_model[model] = next(iter(identities))
    if len(set(checkpoint_by_model.values())) != 3:
        raise ValueError("plain, Coq-only, and CoqView checkpoints are not distinct")
    if not args.plain_selection_evidence.is_file():
        raise ValueError(
            f"plain checkpoint-selection evidence does not exist: "
            f"{args.plain_selection_evidence}"
        )
    summary = {
        "status": "ok",
        "protocol": "disjoint frozen-checkpoint beam10 functional execution",
        "checkpoint_selection": {
            "plain": args.plain_checkpoint_selection,
            "plain_evidence": str(args.plain_selection_evidence),
            "coq": "prespecified final checkpoint after 30 passes",
            "coqview": "prespecified final checkpoint after 10 passes",
        },
        "checkpoint_by_model": checkpoint_by_model,
        "rows": rows,
    }
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    args.markdown_out.write_text(render_markdown(summary) + "\n")


if __name__ == "__main__":
    main()
