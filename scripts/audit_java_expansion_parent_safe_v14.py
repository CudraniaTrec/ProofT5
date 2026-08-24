#!/usr/bin/env python3
"""Independent fail-closed audit for the parent-safe v14 Java expansions."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import pickle
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "Utils" / "data"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "coq_model"))

from scripts.build_java_expansion_mbjp_matched_v10 import gfg_fixture  # noqa: E402
from scripts.build_java_external_datasets import validate_java  # noqa: E402


PAIRS = (
    (
        "humaneval",
        "java_humaneval_mbjp_native_prompt_split80_20_t5gemma2_20260819_v13",
        "java_humaneval_mbjp_native_parent_safe_split80_20_t5gemma2_20260820_v14",
        129,
        33,
    ),
    (
        "transcoder_gfg",
        "java_transcoder_gfg_mbjp_native_prompt_split80_20_t5gemma2_20260819_v13",
        "java_transcoder_gfg_mbjp_native_parent_safe_split80_20_t5gemma2_20260820_v14",
        414,
        103,
    ),
)

PARENT_SPLIT_MANIFEST = (
    DATA / "mbjp_humaneval_half_train_t5gemma2_20260731" / "split_manifest.json"
)


def load_json(path: Path):
    return json.loads(path.read_text())


def load_pickle(path: Path):
    with path.open("rb") as handle:
        return pickle.load(handle)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def proof_map(directory: Path) -> dict[str, dict]:
    result = {}
    for split in ("train", "valid", "test"):
        ids = load_json(directory / f"{split}_task_ids.json")
        rows = load_pickle(directory / f"{split}.pkl")
        if len(ids) != len(rows):
            raise RuntimeError(f"{directory.name}/{split}: proof/ID mismatch")
        for task_id, row in zip(ids, rows):
            if task_id in result:
                raise RuntimeError(f"duplicate proof task ID: {task_id}")
            result[task_id] = row
    return result


def audit_one(
    dataset: str,
    parent_name: str,
    target_name: str,
    train_count: int,
    test_count: int,
    workers: int,
    timeout: int,
    allow_clean_parent_overlap: bool = False,
) -> dict:
    parent = DATA / parent_name
    target = DATA / target_name
    manifest = load_json(target / "parent_safe_split_manifest.json")
    split_manifest = load_json(target / "split_manifest.json")
    parent_rows = load_json(parent / "mbjp_t5.json")
    target_rows = load_json(target / "mbjp_t5.json")
    parent_plain = {row["task_id"]: row for row in parent_rows}
    target_plain = {row["task_id"]: row for row in target_rows}
    parent_proof = proof_map(parent)
    target_proof = proof_map(target)
    tokenizer = load_pickle(target / "tokenizer.pkl")
    split_ids = {
        split: load_json(target / f"{split}_task_ids.json")
        for split in ("train", "valid", "test")
    }
    failures = []

    def fail(stage: str, error: str, task_id: str | None = None) -> None:
        item = {"stage": stage, "error": error}
        if task_id is not None:
            item["task_id"] = task_id
        failures.append(item)

    if manifest != split_manifest:
        fail("manifest", "split manifests differ")
    for key in (
        "selection_uses_model_outputs",
        "selection_uses_checkpoint_scores",
        "selection_uses_execution_outcomes",
        "selection_uses_test_outputs",
        "selection_uses_gold_lexemes_or_literals",
    ):
        if manifest.get(key) is not False:
            fail("selection_policy", f"{key} is not false")
    if manifest.get("selection_uses_gold_ir_grammar_shape") is not True:
        fail("selection_policy", "gold IR grammar-shape use is not disclosed")
    if [len(split_ids[x]) for x in ("train", "valid", "test")] != [
        train_count,
        0,
        test_count,
    ]:
        fail("split", "unexpected train/valid/test counts")
    if split_ids["valid"] or load_pickle(target / "valid.pkl"):
        fail("validation", "validation is not empty")
    train_ids, test_ids = set(split_ids["train"]), set(split_ids["test"])
    if train_ids & test_ids or train_ids | test_ids != set(parent_plain):
        fail("split", "overlap or incomplete population")
    if len(target_plain) != len(target_rows) or set(target_plain) != set(parent_plain):
        fail("identity", "target population differs or has duplicate IDs")
    if list(target_plain) != split_ids["train"] + split_ids["test"]:
        fail("order", "population order does not follow split sidecars")

    clean_parent_ids = set(load_json(PARENT_SPLIT_MANIFEST)["external_train_ids"])
    expected_forced = len(clean_parent_ids & set(parent_plain)) if dataset == "humaneval" else 0
    parent_test_overlap = clean_parent_ids & test_ids if dataset == "humaneval" else set()
    if parent_test_overlap and not allow_clean_parent_overlap:
        fail("parent_leakage", f"clean-673 overlap: {sorted(parent_test_overlap)}")
    expected_forced = 0 if allow_clean_parent_overlap else expected_forced
    if manifest.get("forced_clean673_parent_train_rows") != expected_forced:
        fail("parent_lineage", "unexpected forced clean-673 row count")
    expected_overlap = len(parent_test_overlap) if allow_clean_parent_overlap else 0
    if manifest.get("clean673_parent_train_test_overlap") != expected_overlap:
        fail("parent_lineage", "manifest parent/test overlap count is inconsistent")

    for name, expected in manifest.get("artifact_sha256", {}).items():
        if sha256(target / name) != expected:
            fail("hash", f"artifact hash mismatch: {name}")
    for artifact in ("rules.pkl", "rules.json", "tokenizer.pkl", "coq_tokenizer.pkl"):
        if sha256(parent / artifact) != sha256(target / artifact):
            fail("tokenizer_rules", f"{artifact} changed from v13")

    for task_id, row in target_plain.items():
        expected_split = "train" if task_id in train_ids else "test"
        parent_row = parent_plain[task_id]
        parent_content = {k: v for k, v in parent_row.items() if k not in ("type", "split")}
        target_content = {k: v for k, v in row.items() if k not in ("type", "split")}
        if target_content != parent_content:
            fail("content", "plain content changed from v13", task_id)
        if row.get("type") != expected_split or row.get("split") != expected_split:
            fail("split_field", "plain split/type mismatch", task_id)
        if target_proof[task_id] != parent_proof[task_id]:
            fail("proof", "proof row changed from v13", task_id)
        if target_proof[task_id].get("nl") != tokenizer.encode(row["prompt"]):
            fail("tokenizer", "proof nl does not encode prompt", task_id)
        if target_proof[task_id].get("test") != row["test"]:
            fail("test_alignment", "plain and proof tests differ", task_id)

    for task_id in test_ids:
        row = target_plain[task_id]
        visible = sum(
            line.strip().startswith("* >")
            and re.search(
                rf"\b{re.escape(row['entry_point'])}\s*\(", line
            ) is not None
            for line in row["prompt"].splitlines()
        )
        if visible != 3:
            fail("visible_cases", f"expected 3, found {visible}", task_id)
        if dataset == "humaneval":
            executable = row["test"].count("Exception -- test case")
            if executable != 3:
                fail("executable_cases", f"expected 3, found {executable}", task_id)
        else:
            try:
                values, outputs = gfg_fixture(row)
                if len(outputs) != 3 or any(len(items) != 3 for items in values.values()):
                    fail("executable_cases", "GFG fixture is not exactly 3 cases", task_id)
            except Exception as exc:
                fail("executable_cases", f"GFG fixture parse error: {exc}", task_id)

    def execute(row: dict) -> tuple[str, str | None]:
        try:
            validate_java(row["prompt"] + row["canonical_solution"], row["test"], timeout)
            return row["task_id"], None
        except Exception as exc:
            return row["task_id"], f"{type(exc).__name__}: {exc}"[:900]

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        for task_id, error in executor.map(execute, target_rows):
            if error is not None:
                fail("gold_execution", error, task_id)

    return {
        "dataset": target_name,
        "mbjp_native_parent": parent_name,
        "train_rows": len(train_ids),
        "validation_rows": len(split_ids["valid"]),
        "test_rows": len(test_ids),
        "clean673_parent_train_test_overlap": len(parent_test_overlap),
        "gold_programs_compiled_and_passed": len(target_rows)
        - sum(item["stage"] == "gold_execution" for item in failures),
        "all_test_rows_three_visible_cases": not any(
            item["stage"] == "visible_cases" for item in failures
        ),
        "all_test_rows_three_executable_cases": not any(
            item["stage"] == "executable_cases" for item in failures
        ),
        "failure_count": len(failures),
        "failures": failures,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=24)
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--dataset", choices=("humaneval", "transcoder_gfg"))
    parser.add_argument("--parent-task")
    parser.add_argument("--target-task")
    parser.add_argument("--train-count", type=int)
    parser.add_argument("--test-count", type=int)
    parser.add_argument("--allow-clean-parent-overlap", action="store_true")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs/audits/JAVA_EXPANSION_PARENT_SAFE_V14_AUDIT_20260820.json",
    )
    args = parser.parse_args()
    custom = (
        args.dataset,
        args.parent_task,
        args.target_task,
        args.train_count,
        args.test_count,
    )
    if any(value is not None for value in custom):
        if not all(value is not None for value in custom):
            parser.error(
                "custom audit requires --dataset, --parent-task, --target-task, "
                "--train-count, and --test-count"
            )
        pairs = [custom]
    else:
        pairs = PAIRS
    report = [
        audit_one(
            *pair,
            workers=args.workers,
            timeout=args.timeout,
            allow_clean_parent_overlap=args.allow_clean_parent_overlap,
        )
        for pair in pairs
    ]
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if any(item["failure_count"] for item in report):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
