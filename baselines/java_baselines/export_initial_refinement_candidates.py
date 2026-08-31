from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from baselines.java_baselines.common import CandidateWriter, output_directory


def export_initial_candidates(
    input_dir: Path,
    score_task: str,
    score_split: str,
    output_tag: str,
) -> Path:
    target = output_directory(score_task, score_split, output_tag)
    writer = CandidateWriter(target)
    paths = sorted((input_dir / "trajectories").glob("*.json"))
    if not paths:
        raise FileNotFoundError(f"no trajectories found under {input_dir}")
    for path in paths:
        problem, rank = (int(value) for value in path.stem.split("_"))
        trajectory = json.loads(path.read_text())
        if trajectory.get("method") != "compiler_feedback_refinement":
            raise ValueError(f"not an iterative-refinement trajectory: {path}")
        initial = trajectory["rounds"][0]
        writer.write(
            problem,
            rank,
            initial["source"],
            {
                "method": "compiler_feedback_initial_control",
                "source_trajectory": str(path.resolve()),
                "problem_index": problem,
                "candidate_rank": rank,
                "round": initial,
            },
        )
    writer.write_manifest(
        {
            "schema_version": 1,
            "method": "compiler_feedback_initial_control",
            "source_output_dir": str(input_dir.resolve()),
            "candidate_count": len(paths),
            "score_task": score_task,
            "score_split": score_split,
        }
    )
    print(f"saved initial candidates to {target}")
    return target


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export round-0 candidates from an iterative Java baseline run."
    )
    parser.add_argument("--input_dir", type=Path, required=True)
    parser.add_argument("--score_task", required=True)
    parser.add_argument("--score_split", default="test")
    parser.add_argument("--output_tag", required=True)
    args = parser.parse_args()
    export_initial_candidates(
        args.input_dir, args.score_task, args.score_split, args.output_tag
    )


if __name__ == "__main__":
    main()
