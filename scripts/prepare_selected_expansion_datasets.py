#!/usr/bin/env python3
"""Package the selected HumanEval-131 and synthetic-SuFu-40 test expansions."""

import argparse
import concurrent.futures
import json
import pickle
import re
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_java_external_datasets import validate_java  # noqa: E402


JAVA_TASK = "java_humaneval_external_t5gemma2_20260730"
SUFU_TASKS = [
    "sufu_synthetic_external_t5gemma2_20260730",
    "sufu_synthetic_structural_v2_t5gemma2_20260730",
]
SUFU_COMBINED_TASK = "sufu_synthetic40_external_t5gemma2_20260731"


def load_json(path):
    return json.loads(Path(path).read_text())


def dump_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def load_pickle(path):
    with Path(path).open("rb") as source:
        return pickle.load(source)


def dump_pickle(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as output:
        pickle.dump(value, output)


def description_from_prompt(prompt):
    match = re.search(r"/\*\*(.*?)\*/", prompt, flags=re.S)
    if match is None:
        raise ValueError("Java prompt has no Javadoc description")
    lines = []
    for line in match.group(1).splitlines():
        line = re.sub(r"^\s*\*\s?", "", line).strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


def prepare_java(data_root, selected_root, t5_data_root, workers):
    task_dir = data_root / JAVA_TASK
    accepted = load_pickle(task_dir / "test.pkl")
    accepted_ids = {
        int(row["task_id"].split("/")[-1]): row
        for row in accepted
    }
    readable = []
    baseline = []
    for number in sorted(accepted_ids):
        source = accepted_ids[number]
        task_id = f"Java/{number}"
        description = description_from_prompt(source["source_prompt"])
        readable.append(
            {
                "task_id": task_id,
                "language": "java",
                "description": description,
                "prompt": source["source_prompt"],
                "program": source["java_code"],
                "test": source["test"],
            }
        )
        baseline.append(
            {
                "task_id": task_id,
                "prompt": source["source_prompt"],
                "code": source["java_code"],
                "test": source["test"],
                "type": "test",
            }
        )

    def check(row):
        validate_java(row["program"], row["test"], timeout=20)
        return row["task_id"]

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        checked = list(executor.map(check, readable))
    if len(checked) != 131:
        raise RuntimeError(f"expected 131 Java rows, validated {len(checked)}")

    dump_json(selected_root / "java_humaneval_131.json", readable)
    dump_json(t5_data_root / "humaneval_external131_test_t5.json", baseline)
    return readable


def prepare_sufu(data_root, selected_root, t5_data_root):
    rows = []
    source_by_id = {}
    source_dirs = []
    for task in SUFU_TASKS:
        task_dir = data_root / task
        source_dirs.append(task_dir)
        rows.extend(load_pickle(task_dir / "test.pkl"))
        for source in load_json(task_dir / "source_programs.json"):
            task_id = source["file_name"]
            if task_id in source_by_id:
                raise RuntimeError(f"duplicate SuFu source ID: {task_id}")
            source_by_id[task_id] = source

    ids = [row["file_name"] for row in rows]
    if len(rows) != 40 or len(set(ids)) != 40:
        raise RuntimeError(f"expected 40 unique SuFu rows, found {len(set(ids))}")

    readable = []
    baseline = []
    for row in rows:
        task_id = row["file_name"]
        source = source_by_id[task_id]
        description = source["desc"].strip()
        if not description or not row["code"].strip():
            raise RuntimeError(f"incomplete SuFu record: {task_id}")
        readable.append(
            {
                "task_id": task_id,
                "language": "sufu",
                "description": description,
                "prompt": row["nl_raw"],
                "program": row["code"],
                "tests": row["tests"],
                "expected_output": row["output"],
            }
        )
        baseline.append(
            {
                "task_id": task_id,
                "prompt": row["nl_raw"],
                "code": row["code"],
                "postfix": row["postfix"],
                "tests": row["tests"],
                "output": row["output"],
                "type": "test",
            }
        )

    dump_json(selected_root / "sufu_synthetic_40.json", readable)
    dump_json(t5_data_root / "sufu_synthetic40_test_t5.json", baseline)

    destination = data_root / SUFU_COMBINED_TASK
    if destination.exists():
        raise FileExistsError(f"refusing to overwrite {destination}")
    destination.mkdir(parents=True)
    dump_pickle(destination / "train.pkl", [])
    dump_pickle(destination / "valid.pkl", [])
    dump_pickle(destination / "test.pkl", rows)
    dump_pickle(destination / "all_candidates.pkl", rows)
    dump_json(destination / "train.json", [])
    dump_json(destination / "valid.json", [])
    dump_json(destination / "test.json", rows)
    dump_json(destination / "source_programs.json", readable)

    reference = source_dirs[0]
    for filename in ["rules.pkl", "rules.json", "tokenizer.pkl", "coq_tokenizer.pkl"]:
        shutil.copy2(reference / filename, destination / filename)
    config = load_json(reference / "config.json")
    config.update(
        {
            "evaluation_only": True,
            "validation": False,
            "CodeLen": max(len(row["rulelist"]) for row in rows),
            "max_code_len": max(
                len(row["rulelist"]) - len(row["prefix"])
                for row in rows
            ),
        }
    )
    dump_json(destination / "config.json", config)
    dump_json(
        destination / "conversion_report.json",
        {
            "dataset": SUFU_COMBINED_TASK,
            "policy": "held-out evaluation only",
            "sources": SUFU_TASKS,
            "checked": 40,
            "passed": 40,
            "failed": 0,
            "task_ids": ids,
        },
    )
    return readable


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, default=ROOT / "Utils" / "data")
    parser.add_argument(
        "--selected-root",
        type=Path,
        default=ROOT / "selected_data" / "expansion_20260731",
    )
    parser.add_argument("--t5-data-root", type=Path, default=ROOT / "t5_llm" / "data")
    parser.add_argument("--java-workers", type=int, default=24)
    return parser.parse_args()


def main():
    args = parse_args()
    for path in [
        args.selected_root / "java_humaneval_131.json",
        args.selected_root / "sufu_synthetic_40.json",
        args.t5_data_root / "humaneval_external131_test_t5.json",
        args.t5_data_root / "sufu_synthetic40_test_t5.json",
    ]:
        if path.exists():
            raise FileExistsError(f"refusing to overwrite {path}")

    java = prepare_java(
        args.data_root,
        args.selected_root,
        args.t5_data_root,
        args.java_workers,
    )
    sufu = prepare_sufu(args.data_root, args.selected_root, args.t5_data_root)
    dump_json(
        args.selected_root / "manifest.json",
        {
            "policy": "held-out evaluation only",
            "java": {
                "dataset": "HumanEval",
                "rows": len(java),
                "proof_task": JAVA_TASK,
                "readable_file": "java_humaneval_131.json",
                "baseline_file": "t5_llm/data/humaneval_external131_test_t5.json",
            },
            "sufu": {
                "dataset": "synthetic v1 + structural v2",
                "rows": len(sufu),
                "proof_task": SUFU_COMBINED_TASK,
                "readable_file": "sufu_synthetic_40.json",
                "baseline_file": "t5_llm/data/sufu_synthetic40_test_t5.json",
            },
        },
    )
    print(f"prepared Java HumanEval: {len(java)} test rows")
    print(f"prepared synthetic SuFu: {len(sufu)} test rows")


if __name__ == "__main__":
    main()
