from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from baselines.java_baselines.common import (
    REPO_ROOT,
    align_tasks_to_score,
    load_java_tasks,
    select_tasks,
    sha256_file,
)


def prompt_sha256(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def parse_spec(value: str) -> tuple[Path, str, str, str]:
    parts = value.split("::")
    if len(parts) != 4:
        raise argparse.ArgumentTypeError(
            "task specs must be DATASET_JSON::SCORE_TASK::SPLIT::INDICES"
        )
    dataset, score_task, split, indices = parts
    if not dataset or not score_task or not split or not indices:
        raise argparse.ArgumentTypeError("task spec fields cannot be empty")
    return Path(dataset), score_task, split, indices


def export_bundle(specs: list[tuple[Path, str, str, str]], output: Path) -> dict:
    if output.exists():
        raise FileExistsError(f"refusing to overwrite prompt bundle: {output}")
    records = []
    for dataset_path, score_task, split, indices in specs:
        tasks, score_dataset_path = align_tasks_to_score(
            load_java_tasks(dataset_path, split), score_task, split
        )
        selected = select_tasks(tasks, indices, 0)
        for task in selected:
            records.append(
                {
                    "dataset_json": str(dataset_path.resolve()),
                    "dataset_sha256": sha256_file(dataset_path),
                    "score_task": score_task,
                    "score_split": split,
                    "score_dataset_sha256": sha256_file(score_dataset_path),
                    "problem_index": task.index,
                    "task_id": task.task_id,
                    "prompt": task.prompt,
                    "prompt_sha256": prompt_sha256(task.prompt),
                    "requested_output": (
                        "missing Java suffix from the exact final prompt character"
                    ),
                }
            )
    bundle = {
        "schema_version": 1,
        "privacy_contract": (
            "Contains prompts only. Hidden test harnesses and expected outputs are excluded."
        ),
        "tasks": records,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(bundle, indent=2, sort_keys=True))
    return bundle


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export a test-free prompt bundle for an online model smoke test."
    )
    parser.add_argument("--task_spec", action="append", type=parse_spec, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    bundle = export_bundle(args.task_spec, args.output)
    print(
        {
            "output": str(args.output),
            "tasks": len(bundle["tasks"]),
            "tests_exposed": False,
        }
    )


if __name__ == "__main__":
    main()
