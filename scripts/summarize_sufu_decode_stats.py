"""Aggregate decode statistics collected by the instrumented SuFu beam search.

Reads the JSONL emitted by beamsearch_sufu.py (PROOFT5_COLLECT_DECODE_STATS=1)
and prints the RQ2 pruning-rate summary: syntax-stage mask survival, type-stage
(derivation-extension) rejection, completion-guard rejection, beam exhaustion,
decode steps, and per-problem candidate counts.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stats_jsonl")
    args = parser.parse_args()

    problems: dict[str, dict] = {}
    run_meta: dict = {}
    for line in Path(args.stats_jsonl).read_text().splitlines():
        record = json.loads(line)
        run_meta = {k: record[k] for k in record if k != "problems"}
        for pid, stats in record["problems"].items():
            if pid in problems:
                raise RuntimeError(f"duplicate problem id across shards: {pid}")
            problems[pid] = stats

    total_syntax_sum = sum(p["syntax_valid_sum"] for p in problems.values())
    total_syntax_n = sum(p["syntax_samples"] for p in problems.values())
    syntax_survival = total_syntax_sum / total_syntax_n if total_syntax_n else 0.0

    total_attempted = sum(p["expansions_attempted"] for p in problems.values())
    total_apply_rej = sum(p["apply_rejected"] for p in problems.values())
    total_guard_checks = sum(p["completion_guard_checks"] for p in problems.values())
    total_guard_rej = sum(p["completion_guard_rejected"] for p in problems.values())
    total_added = sum(p["finished_added"] for p in problems.values())

    outcomes = Counter(p.get("outcome", "missing") for p in problems.values())
    steps = [p.get("steps", 0) for p in problems.values()]
    cands = [p.get("candidates", 0) for p in problems.values()]

    per_problem_syntax = sorted(
        (p["syntax_valid_sum"] / p["syntax_samples"]) if p["syntax_samples"] else 0.0
        for p in problems.values()
    )
    per_problem_apply = sorted(
        (p["apply_rejected"] / p["expansions_attempted"])
        if p["expansions_attempted"]
        else 0.0
        for p in problems.values()
    )

    def pct(x: float) -> str:
        return f"{100 * x:.2f}%"

    def quantile(xs, q):
        if not xs:
            return 0.0
        idx = min(len(xs) - 1, max(0, round(q * (len(xs) - 1))))
        return xs[idx]

    print(f"problems: {len(problems)}  meta: {run_meta}")
    print(f"syntax-stage mask survival (fraction of vocab allowed per beam-step):")
    print(
        f"  overall mean = {syntax_survival:.4f}  -> mean syntax pruning rate = {pct(1 - syntax_survival)}"
    )
    print(
        f"  per-problem survival quantiles: min={per_problem_syntax[0]:.4f} "
        f"q25={quantile(per_problem_syntax, 0.25):.4f} median={quantile(per_problem_syntax, 0.5):.4f} "
        f"q75={quantile(per_problem_syntax, 0.75):.4f} max={per_problem_syntax[-1]:.4f}"
    )
    print(
        f"type-stage (derivation-extension apply) rejections among grammar-surviving expansions:"
    )
    print(
        f"  {total_apply_rej}/{total_attempted} = {pct(total_apply_rej / total_attempted if total_attempted else 0)}"
    )
    print(
        f"  per-problem rejection quantiles: min={pct(per_problem_apply[0])} "
        f"median={pct(quantile(per_problem_apply, 0.5))} max={pct(per_problem_apply[-1])}"
    )
    print("completion type-guard rejections (whole-program + surface recheck):")
    print(
        f"  {total_guard_rej}/{total_guard_checks} = {pct(total_guard_rej / total_guard_checks if total_guard_checks else 0)}"
        f"   (finished added: {total_added})"
    )
    print(f"outcomes: {dict(outcomes)}")
    full = sum(1 for c in cands if c >= 10)
    print(
        f"steps: mean={sum(steps) / len(steps):.1f} max={max(steps)}; "
        f"candidates: mean={sum(cands) / len(cands):.1f} "
        f"problems with 10 candidates: {full}/{len(cands)}; "
        f"total slots missing: {sum(max(0, 10 - c) for c in cands)}"
    )

    out = Path(args.stats_jsonl).with_suffix(".summary.json")
    out.write_text(
        json.dumps(
            {
                "problems": len(problems),
                "run_meta": run_meta,
                "syntax_survival_mean": syntax_survival,
                "syntax_pruning_rate": 1 - syntax_survival,
                "syntax_survival_per_problem": per_problem_syntax,
                "expansions_attempted": total_attempted,
                "apply_rejected": total_apply_rej,
                "apply_rejection_rate": total_apply_rej / total_attempted if total_attempted else 0,
                "completion_guard_checks": total_guard_checks,
                "completion_guard_rejected": total_guard_rej,
                "completion_guard_rejection_rate": total_guard_rej / total_guard_checks if total_guard_checks else 0,
                "outcomes": dict(outcomes),
                "steps_mean": sum(steps) / len(steps),
                "problems_with_full_candidates": full,
                "missing_candidate_slots": sum(max(0, 10 - c) for c in cands),
            },
            indent=2,
        )
    )
    print(f"summary written to {out}")


if __name__ == "__main__":
    main()
