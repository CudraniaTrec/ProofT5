"""Paired significance analysis for the 2B SuFu rerun (Appendix D method).

Consumes two score JSONs from score_sufu_no_write.py (baseline plain
T5Gemma2-2B and TyFlow-2B) plus their candidate output directories, and
computes the same statistics the paper's appendix reports:

- pass@1 / pass@10: exact two-sided McNemar (binomial on discordant pairs)
- FSP: exact two-sided sign test on nonzero paired differences, plus 95%
  t-intervals over per-task ranks
- CER: exact two-sided sign test on per-task compilation-error fractions
- Wilson 95% intervals for pass rates (over tasks) and CER (over candidates)

Usage:
  python scripts/compute_2b_sufu_paired_stats_20260915.py \
    --baseline-json <score.json> --baseline-out <output_dir> \
    --tyflow-json <score.json> --tyflow-out <output_dir> \
    --json-out <result.json>
"""

import argparse
import json
import math
import os
from collections import Counter

PASS_K = 10


def binom_two_sided(k, n):
    """Exact two-sided sign/McNemar p: double the small binomial tail."""
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(min(k, n - k) + 1)) / (2.0**n)
    return min(1.0, 2.0 * tail)


def wilson(successes, total, z=1.959963984540054):
    if total == 0:
        return [0.0, 0.0]
    p = successes / total
    denom = 1 + z * z / total
    centre = p + z * z / (2 * total)
    spread = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total))
    return [100.0 * (centre - spread) / denom, 100.0 * (centre + spread) / denom]


def t_interval(values, t=2.0024654557967746):
    """95% t-interval over per-task values (t_{57,0.975})."""
    n = len(values)
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / (n - 1)
    half = t * math.sqrt(var / n)
    return [mean - half, mean + half]


def per_problem_statuses(output_dir, score):
    """Rebuild per-problem candidate statuses from the score record.

    Compile errors / timeouts come from the score JSON id lists; candidate
    file presence gives missing; error_solution() text rules give ignored;
    the remainder splits into success (from solved/first_success_pos) and
    failed.
    """
    solved = set(score["solved"])
    first_pos = {pid: pos for pid, pos in zip(score["problem_ids"], score["first_success_pos"])}
    ce_ids = Counter()
    for pid, cand in score.get("compile_error_candidate_ids") or []:
        ce_ids[pid] += 1
    to_ids = Counter()
    for pid, cand in score.get("timeout_candidate_ids") or []:
        to_ids[pid] += 1

    def is_error_solution(text):
        if "IndexError" in text:
            return True
        if "GrammarError" in text:
            return False
        return "??" in text

    per_problem = {}
    for pid in score["problem_ids"]:
        statuses = []
        for cand in range(PASS_K):
            path = None
            for ext in ("java", "txt"):
                candidate = os.path.join(output_dir, f"{pid}_{cand}.{ext}")
                if os.path.exists(candidate):
                    path = candidate
                    break
            if path is None:
                statuses.append("missing")
                continue
            if is_error_solution(open(path, "r").read()):
                statuses.append("ignored")
                continue
            statuses.append(None)  # executed; classify below
        executed = [i for i, s in enumerate(statuses) if s is None]
        # Re-classify executed slots.
        ce = to_ce = 0
        success_positions = set()
        if pid in solved:
            pos = first_pos[pid]
            success_positions.add(pos)
            # Other successes are unknown individually; only the first is
            # recorded. For FSP only the first matters, and for CER fractions
            # we need error counts, which we have from the id lists.
        for i in list(executed):
            pass
        per_problem[pid] = {
            "statuses": statuses,
            "executed": len(executed),
            "compile_errors": ce_ids[pid],
            "timeouts": to_ids[pid],
            "first_success": first_pos.get(pid, PASS_K),
            "solved": pid in solved,
        }
    return per_problem


def load_side(score_path, output_dir):
    score = json.load(open(score_path))
    assert score["pass_at_k"] == PASS_K
    per_problem = per_problem_statuses(output_dir, score)
    pass1 = [1 if pid in set(score["solved"]) and score["first_success_pos"][i] == 0 else 0
             for i, pid in enumerate(score["problem_ids"])]
    pass10 = [1 if pid in set(score["solved"]) else 0 for i, pid in enumerate(score["problem_ids"])]
    fsp = list(score["first_success_pos"])
    cer_frac = []
    for pid in score["problem_ids"]:
        info = per_problem[pid]
        tested = info["executed"]
        cer_frac.append(info["compile_errors"] / tested if tested else 0.0)
    return {
        "score": score,
        "problem_ids": list(score["problem_ids"]),
        "pass1": pass1,
        "pass10": pass10,
        "fsp": fsp,
        "cer_frac": cer_frac,
    }


def paired_report(base, ty):
    assert base["problem_ids"] == ty["problem_ids"]
    report = {}
    for metric in ("pass1", "pass10"):
        b, t = base[metric], ty[metric]
        b_only = sum(1 for x, y in zip(b, t) if x and not y)
        t_only = sum(1 for x, y in zip(b, t) if y and not x)
        n = b_only + t_only
        report[metric] = {
            "baseline_solved": sum(b),
            "tyflow_solved": sum(t),
            "discordant_baseline_only": b_only,
            "discordant_tyflow_only": t_only,
            "p_value": binom_two_sided(t_only, n),
        }
    diffs = [y - x for x, y in zip(base["fsp"], ty["fsp"]) if y != x]
    better = sum(1 for d in diffs if d < 0)
    worse = sum(1 for d in diffs if d > 0)
    report["fsp"] = {
        "baseline_mean": sum(base["fsp"]) / len(base["fsp"]),
        "tyflow_mean": sum(ty["fsp"]) / len(ty["fsp"]),
        "better": better,
        "worse": worse,
        "nonzero_pairs": len(diffs),
        "p_value": binom_two_sided(better, len(diffs)),
        "baseline_t_interval": t_interval(base["fsp"]),
        "tyflow_t_interval": t_interval(ty["fsp"]),
    }
    cer_diffs = [y - x for x, y in zip(base["cer_frac"], ty["cer_frac"]) if abs(y - x) > 1e-12]
    cer_better = sum(1 for d in cer_diffs if d < 0)
    cer_worse = sum(1 for d in cer_diffs if d > 0)
    report["cer"] = {
        "baseline_errors": base["score"]["compile_errors"],
        "baseline_tested": base["score"]["total_tested"],
        "tyflow_errors": ty["score"]["compile_errors"],
        "tyflow_tested": ty["score"]["total_tested"],
        "better": cer_better,
        "worse": cer_worse,
        "nonzero_pairs": len(cer_diffs),
        "p_value": binom_two_sided(cer_better, len(cer_diffs)),
    }
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-json", required=True)
    parser.add_argument("--baseline-out", required=True)
    parser.add_argument("--tyflow-json", required=True)
    parser.add_argument("--tyflow-out", required=True)
    parser.add_argument("--json-out", required=True)
    args = parser.parse_args()

    base = load_side(args.baseline_json, args.baseline_out)
    ty = load_side(args.tyflow_json, args.tyflow_out)
    report = {
        "baseline": {k: base["score"][k] for k in (
            "task", "output_tag", "model_checkpoint_path",
            "model_checkpoint_sha256", "pass1", "pass10",
            "compile_error_rate", "compile_errors", "total_tested",
            "average_first_success_position", "timeouts", "ignored",
            "missing")},
        "tyflow": {k: ty["score"][k] for k in (
            "task", "output_tag", "model_checkpoint_path",
            "model_checkpoint_sha256", "pass1", "pass10",
            "compile_error_rate", "compile_errors", "total_tested",
            "average_first_success_position", "timeouts", "ignored",
            "missing")},
        "wilson_intervals": {
            "baseline": {
                "pass1": wilson(sum(base["pass1"]), len(base["pass1"])),
                "pass10": wilson(sum(base["pass10"]), len(base["pass10"])),
                "cer": wilson(base["score"]["compile_errors"], base["score"]["total_tested"]),
            },
            "tyflow": {
                "pass1": wilson(sum(ty["pass1"]), len(ty["pass1"])),
                "pass10": wilson(sum(ty["pass10"]), len(ty["pass10"])),
                "cer": wilson(ty["score"]["compile_errors"], ty["score"]["total_tested"]),
            },
        },
        "paired_tests": paired_report(base, ty),
        "arrays": {
            "problem_ids": base["problem_ids"],
            "baseline": {
                "solved": base["score"]["solved"],
                "top1_solved": base["score"]["top1_solved"],
                "first_success_pos": base["fsp"],
                "cer_fractions": base["cer_frac"],
            },
            "tyflow": {
                "solved": ty["score"]["solved"],
                "top1_solved": ty["score"]["top1_solved"],
                "first_success_pos": ty["fsp"],
                "cer_fractions": ty["cer_frac"],
            },
        },
    }
    with open(args.json_out, "w") as handle:
        json.dump(report, handle, indent=1, sort_keys=True)
    print(json.dumps({k: report[k] for k in ("baseline", "tyflow", "paired_tests")}, indent=1))


if __name__ == "__main__":
    main()
