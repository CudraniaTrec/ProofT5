"""Assemble a rejection-sampling candidate set from generation arms.

Policy: for each problem, candidates are drawn arm by arm in a fixed order
(round 1 = the frozen ordinary control, then resample rounds with distinct
seeds).  Every draw is checked with standalone ``javac``; uncompilable draws
are rejected and resampling continues until ten compilable candidates are
collected or the arm budget is exhausted.  Benchmark tests are never executed
during selection.  Slots that remain unfilled after the budget are left
missing so the scorer counts them as failures (fail-closed).
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import sys
import time
from collections import Counter
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from baselines.java_baselines.common import (
    CandidateWriter,
    compile_java_source,
    sha256_file,
)


def candidate_paths(root: Path) -> dict[tuple[int, int], Path]:
    inventory: dict[tuple[int, int], Path] = {}
    for path in root.glob("*_*.txt"):
        problem, rank = (int(value) for value in path.stem.split("_", 1))
        inventory[(problem, rank)] = path
    return inventory


def check(identity_and_path, timeout: float, javac: str | None):
    identity, path = identity_and_path
    source = path.read_text()
    result = compile_java_source(source, timeout=timeout, javac=javac)
    return identity, source, result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control_dir", required=True, help="round-1 ordinary candidates")
    parser.add_argument(
        "--resample_dirs",
        default="",
        help="comma-separated resample arm candidate dirs, in draw order",
    )
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--expected_problems", type=int, required=True)
    parser.add_argument("--expected_candidates", type=int, default=10)
    parser.add_argument(
        "--max_arms_per_problem",
        type=int,
        default=4,
        help="maximum number of ten-draw arms a problem may consume",
    )
    parser.add_argument("--workers", type=int, default=32)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--javac", default="")
    args = parser.parse_args()

    control_root = Path(args.control_dir).resolve()
    arm_roots = [control_root] + [
        Path(part).resolve() for part in args.resample_dirs.split(",") if part.strip()
    ]
    target = Path(args.output_dir).resolve()
    if target.exists():
        raise FileExistsError(f"refusing to overwrite output: {target}")

    problems = args.expected_problems
    ranks = args.expected_candidates
    expected_control = {(p, r) for p in range(problems) for r in range(ranks)}
    control_inventory = candidate_paths(control_root)
    if set(control_inventory) != expected_control:
        raise RuntimeError(
            "control candidate inventory mismatch: "
            f"missing={sorted(expected_control - set(control_inventory))[:10]}"
        )
    arm_inventories = [control_inventory] + [
        candidate_paths(root) for root in arm_roots[1:]
    ]

    # Compile-check every candidate that could be drawn.
    jobs: dict[tuple[int, int, int], tuple[tuple[int, int], Path]] = {}
    for arm, inventory in enumerate(arm_inventories):
        for identity, path in inventory.items():
            jobs[(arm, *identity)] = (identity, path)
    started = time.perf_counter()
    compile_results: dict[tuple[int, int, int], object] = {}
    sources: dict[tuple[int, int, int], str] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        future_map = {
            pool.submit(check, job, args.timeout, args.javac or None): key
            for key, job in jobs.items()
        }
        for future in concurrent.futures.as_completed(future_map):
            key = future_map[future]
            identity, source, result = future.result()
            compile_results[key] = result
            sources[key] = source
    compile_seconds = time.perf_counter() - started

    writer = CandidateWriter(target, resume=False)
    per_problem_kept: dict[int, int] = {}
    per_problem_draws: dict[int, int] = {}
    kept_from_arm: Counter = Counter()
    total_kept = 0
    total_missing = 0
    for problem in range(problems):
        kept = 0
        draws = 0
        for arm, inventory in enumerate(arm_inventories):
            if arm >= args.max_arms_per_problem:
                break
            for rank in range(ranks):
                key = (arm, problem, rank)
                if key not in compile_results:
                    continue
                draws += 1
                result = compile_results[key]
                if not result.success:
                    continue
                if kept >= ranks:
                    break
                writer.write(
                    problem,
                    kept,
                    sources[key],
                    {
                        "method": "rejection_sampling",
                        "problem_index": problem,
                        "candidate_rank": kept,
                        "source_arm": arm,
                        "source_rank": rank,
                        "selection_policy": (
                            "draws are checked with standalone javac; uncompilable "
                            "draws are rejected until ten compilable candidates are "
                            "collected or the arm budget is exhausted; benchmark "
                            "tests are never executed during selection"
                        ),
                        "compile": result.__dict__,
                    },
                )
                kept += 1
                kept_from_arm[arm] += 1
                if kept >= ranks:
                    break
        per_problem_kept[problem] = kept
        per_problem_draws[problem] = draws
        total_kept += kept
        total_missing += ranks - kept

    filled = sum(1 for kept in per_problem_kept.values() if kept == ranks)
    writer.write_manifest(
        {
            "schema_version": 1,
            "method": "rejection_sampling",
            "control_dir": str(control_root),
            "control_manifest_sha256": sha256_file(control_root / "baseline_manifest.json"),
            "resample_dirs": [str(root) for root in arm_roots[1:]],
            "selection_policy": (
                "per problem, keep the first ten javac-compilable draws in arm "
                "order; unfilled slots stay missing and count as failures"
            ),
            "max_arms_per_problem": args.max_arms_per_problem,
            "candidate_budget": ranks,
            "problems": problems,
            "problems_fully_filled": filled,
            "total_kept_candidates": total_kept,
            "total_missing_slots": total_missing,
            "kept_from_arm": dict(sorted(kept_from_arm.items())),
            "total_draws": sum(per_problem_draws.values()),
            "compile_check_seconds": compile_seconds,
            "arguments": vars(args),
        }
    )
    print(
        f"assembled {total_kept} candidates ({total_missing} missing slots, "
        f"{filled}/{problems} problems fully filled); kept per arm "
        f"{dict(sorted(kept_from_arm.items()))}"
    )


if __name__ == "__main__":
    main()
