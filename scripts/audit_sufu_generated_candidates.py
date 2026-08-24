#!/usr/bin/env python3
"""Audit SuFu beam outputs at the exact write/scoring boundary."""

import argparse
import json
import math
import pickle
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from SuFu.sufu_model import TypeCtx, parser, visit


CANDIDATE_RE = re.compile(r"^(\d+)_(\d+)\.txt$")


def validate_surface_program(code):
    tree = parser.parse(code.encode("utf-8"))
    if tree.root_node.has_error:
        raise AssertionError(tree.root_node.sexp())
    visit(tree.root_node, {"code": code}).type_check(TypeCtx())


def audit_output_dir(
    output_dir,
    problem_count,
    beam_size,
    require_beam_metadata,
    selected_problem_ids=None,
):
    if selected_problem_ids is None:
        selected_problem_ids = list(range(problem_count))
    selected_problem_ids = sorted(int(problem_id) for problem_id in selected_problem_ids)
    if len(selected_problem_ids) != len(set(selected_problem_ids)):
        raise ValueError("selected_problem_ids contains duplicates")
    invalid_selection = [
        problem_id
        for problem_id in selected_problem_ids
        if problem_id < 0 or problem_id >= problem_count
    ]
    if invalid_selection:
        raise ValueError(f"selected problem ids out of range: {invalid_selection}")
    candidates = {problem_id: {} for problem_id in selected_problem_ids}
    unexpected_candidate_ids = []
    for path in output_dir.glob("*.txt"):
        match = CANDIDATE_RE.match(path.name)
        if not match:
            continue
        problem_id, candidate_id = map(int, match.groups())
        if problem_id not in candidates:
            unexpected_candidate_ids.append([problem_id, candidate_id])
            continue
        candidates[problem_id][candidate_id] = path

    missing_top0 = []
    noncontiguous = []
    invalid = []
    metadata_errors = []
    candidate_counts = []
    for problem_id in selected_problem_ids:
        by_id = candidates[problem_id]
        ids = sorted(by_id)
        candidate_counts.append(len(ids))
        if not ids or ids[0] != 0:
            missing_top0.append(problem_id)
        if ids != list(range(len(ids))) or len(ids) > beam_size:
            noncontiguous.append({"problem_id": problem_id, "candidate_ids": ids})
        for candidate_id, path in sorted(by_id.items()):
            try:
                validate_surface_program(path.read_text())
            except Exception as exc:
                invalid.append(
                    {
                        "problem_id": problem_id,
                        "candidate_id": candidate_id,
                        "error": str(exc),
                    }
                )

        metadata_path = output_dir / f"{problem_id}_beam_scores.json"
        if not metadata_path.exists():
            if require_beam_metadata:
                metadata_errors.append(
                    {"problem_id": problem_id, "error": "missing metadata"}
                )
            continue
        try:
            metadata = json.loads(metadata_path.read_text())
            rows = metadata["candidates"]
            if metadata["problem_id"] != problem_id:
                raise AssertionError("problem_id mismatch")
            if metadata["beam_size"] != beam_size:
                raise AssertionError("beam_size mismatch")
            if len(rows) != len(ids):
                raise AssertionError("candidate count mismatch")
            scores = []
            for row in rows:
                raw = float(row["raw_log_probability"])
                score = float(row["normalized_score"])
                length = int(row["scoring_length"])
                penalty = float(row["length_penalty"])
                if length <= 0 or penalty < 0:
                    raise AssertionError("invalid scoring length/penalty")
                expected = raw / (length**penalty)
                if not math.isclose(score, expected, rel_tol=1e-9, abs_tol=1e-9):
                    raise AssertionError("normalized score mismatch")
                scores.append(score)
            if scores != sorted(scores, reverse=True):
                raise AssertionError("beam scores are not descending")
        except Exception as exc:
            metadata_errors.append(
                {"problem_id": problem_id, "error": str(exc)}
            )

    report = {
        "output_dir": str(output_dir),
        "dataset_problems": problem_count,
        "problems": len(selected_problem_ids),
        "problem_ids": selected_problem_ids,
        "beam_size": beam_size,
        "candidate_files": sum(candidate_counts),
        "candidate_counts": candidate_counts,
        "missing_top0": missing_top0,
        "noncontiguous": noncontiguous,
        "invalid_surface_candidates": invalid,
        "unexpected_candidate_ids": unexpected_candidate_ids,
        "metadata_errors": metadata_errors,
    }
    failures = (
        missing_top0
        or noncontiguous
        or invalid
        or unexpected_candidate_ids
        or metadata_errors
    )
    return report, not failures


def main():
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("--task", required=True)
    arg_parser.add_argument("--split", choices=["train", "valid", "test"], required=True)
    arg_parser.add_argument("--output_tag", required=True)
    arg_parser.add_argument("--beam_size", type=int, required=True)
    arg_parser.add_argument("--indices", default="")
    arg_parser.add_argument("--require_beam_metadata", action="store_true")
    arg_parser.add_argument("--json_out", type=Path, required=True)
    args = arg_parser.parse_args()

    data_path = Path("Utils/data") / args.task / f"{args.split}.pkl"
    output_dir = Path("Utils/output") / f"{args.task}_{args.split}_ans" / args.output_tag
    if not data_path.is_file():
        raise SystemExit(f"dataset absent: {data_path}")
    if not output_dir.is_dir():
        raise SystemExit(f"output directory absent: {output_dir}")
    problem_count = len(pickle.loads(data_path.read_bytes()))
    selected_problem_ids = None
    if args.indices:
        selected_problem_ids = [
            int(value) for value in args.indices.split(",") if value.strip()
        ]
    report, passed = audit_output_dir(
        output_dir,
        problem_count,
        args.beam_size,
        args.require_beam_metadata,
        selected_problem_ids,
    )
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    if not passed:
        raise SystemExit("SuFu generated-candidate audit failed")


if __name__ == "__main__":
    main()
