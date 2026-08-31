from __future__ import annotations

import argparse
import concurrent.futures
import json
import sys
import time
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


def compile_pair(identity, ordinary_path, constrained_path, timeout, javac):
    ordinary_source = ordinary_path.read_text()
    ordinary = compile_java_source(ordinary_source, timeout=timeout, javac=javac)
    constrained_source = constrained_path.read_text()
    constrained = None
    if not ordinary.success:
        constrained = compile_java_source(
            constrained_source, timeout=timeout, javac=javac
        )
    use_constrained = bool(constrained is not None and constrained.success)
    return identity, ordinary_source, constrained_source, ordinary, constrained, use_constrained


def build(args: argparse.Namespace) -> Path:
    ordinary_root = Path(args.ordinary_dir).resolve()
    constrained_root = Path(args.constrained_dir).resolve()
    target = Path(args.output_dir).resolve()
    if target.exists():
        raise FileExistsError(f"refusing to overwrite portfolio output: {target}")

    ordinary = candidate_paths(ordinary_root)
    constrained = candidate_paths(constrained_root)
    if ordinary.keys() != constrained.keys():
        raise RuntimeError("ordinary/constrained candidate identity mismatch")
    expected = {
        (problem, rank)
        for problem in range(args.expected_problems)
        for rank in range(args.expected_candidates)
    }
    if ordinary.keys() != expected:
        raise RuntimeError(
            f"candidate inventory mismatch: missing={sorted(expected-ordinary.keys())[:20]} "
            f"extra={sorted(ordinary.keys()-expected)[:20]}"
        )

    writer = CandidateWriter(target, resume=False)
    method = f"{args.constraint_name}_compile_safe_portfolio"
    started = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [
            pool.submit(
                compile_pair,
                identity,
                ordinary[identity],
                constrained[identity],
                args.timeout,
                args.javac or None,
            )
            for identity in sorted(expected)
        ]
        results = [future.result() for future in futures]

    replacements = 0
    compile_seconds = 0.0
    for identity, ordinary_source, constrained_source, ordinary_result, constrained_result, use_constrained in results:
        problem, rank = identity
        ordinary_trajectory = json.loads(
            (ordinary_root / "trajectories" / f"{problem}_{rank}.json").read_text()
        )
        constrained_trajectory = json.loads(
            (constrained_root / "trajectories" / f"{problem}_{rank}.json").read_text()
        )
        compile_seconds += ordinary_result.elapsed_seconds
        if constrained_result is not None:
            compile_seconds += constrained_result.elapsed_seconds
        replacements += int(use_constrained)
        chosen_source = constrained_source if use_constrained else ordinary_source
        writer.write(
            problem,
            rank,
            chosen_source,
            {
                "method": method,
                "problem_index": problem,
                "candidate_rank": rank,
                "selection": "constrained" if use_constrained else "ordinary",
                "selection_policy": (
                    "replace only when standalone javac rejects the ordinary source "
                    f"and accepts the {args.constraint_name} source; no benchmark "
                    "tests are executed"
                ),
                "ordinary_compile": ordinary_result.__dict__,
                "constrained_compile": (
                    constrained_result.__dict__
                    if constrained_result is not None
                    else None
                ),
                "ordinary_trajectory": str(
                    ordinary_root / "trajectories" / f"{problem}_{rank}.json"
                ),
                "constrained_trajectory": str(
                    constrained_root / "trajectories" / f"{problem}_{rank}.json"
                ),
                "ordinary_generation_seconds": ordinary_trajectory.get(
                    "elapsed_seconds"
                ),
                "constrained_generation_seconds": constrained_trajectory.get(
                    "elapsed_seconds"
                ),
                "compile_gate_seconds": ordinary_result.elapsed_seconds
                + (
                    constrained_result.elapsed_seconds
                    if constrained_result is not None
                    else 0.0
                ),
                "elapsed_seconds": ordinary_trajectory.get("elapsed_seconds", 0.0)
                + constrained_trajectory.get("elapsed_seconds", 0.0)
                + ordinary_result.elapsed_seconds
                + (
                    constrained_result.elapsed_seconds
                    if constrained_result is not None
                    else 0.0
                ),
            },
        )

    writer.write_manifest(
        {
            "schema_version": 1,
            "method": method,
            "ordinary_output_dir": str(ordinary_root),
            "constrained_output_dir": str(constrained_root),
            "ordinary_manifest_sha256": sha256_file(
                ordinary_root / "baseline_manifest.json"
            ),
            "constrained_manifest_sha256": sha256_file(
                constrained_root / "baseline_manifest.json"
            ),
            "selection_policy": (
                "retain ordinary unless standalone javac rejects ordinary and accepts "
                f"{args.constraint_name}; hidden benchmark tests are never run during "
                "selection"
            ),
            "constraint_name": args.constraint_name,
            "candidate_budget": args.expected_candidates,
            "lm_generation_budget_multiplier": 2,
            "candidate_count": len(results),
            "constrained_replacements": replacements,
            "compile_gate_seconds": compile_seconds,
            "build_wall_seconds": time.perf_counter() - started,
            "arguments": vars(args),
        }
    )
    print(f"saved compile-safe portfolio to {target} ({replacements} replacements)")
    return target


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a no-hidden-test compile-safe ordinary/SynCode portfolio."
    )
    parser.add_argument("--ordinary_dir", required=True)
    parser.add_argument("--constrained_dir", required=True)
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--expected_problems", type=int, required=True)
    parser.add_argument("--expected_candidates", type=int, required=True)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--javac", default="")
    parser.add_argument(
        "--constraint_name",
        choices=["syncode_java_cfg", "repilot_jdt"],
        default="syncode_java_cfg",
    )
    build(parser.parse_args())


if __name__ == "__main__":
    main()
