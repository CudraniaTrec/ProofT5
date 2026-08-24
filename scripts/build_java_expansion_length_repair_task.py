#!/usr/bin/env python3
"""Build a train-only Java expansion curriculum with deterministic length replay.

Every unique source training row is retained.  Additional occurrences are
sampled only from training metadata, with fixed weights for source-local IR
length quartile and complex Java signatures.  Validation and test remain
empty; no test row, output, model candidate, or execution result is read.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pickle
import random
import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "Utils" / "data"
ARTIFACTS = ("rules.pkl", "rules.json", "tokenizer.pkl", "coq_tokenizer.pkl")


def load_pickle(path: Path):
    with path.open("rb") as handle:
        return pickle.load(handle)


def dump_pickle(value, path: Path) -> None:
    with path.open("wb") as handle:
        pickle.dump(value, handle, protocol=pickle.HIGHEST_PROTOCOL)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def complex_signature(row: dict) -> bool:
    match = re.search(
        r"public\s+static\s+(.+?)\s+[A-Za-z_$][\w$]*\s*\((.*?)\)\s*\{",
        row["prompt"],
        flags=re.DOTALL,
    )
    if match is None:
        raise RuntimeError(f"cannot parse Java signature: {row.get('task_id')}")
    signature = f"{match.group(1)} {match.group(2)}"
    return any(token in signature for token in ("[]", "List<", "Set<", "Map<")) or (
        bool(match.group(2).strip()) and "," in match.group(2)
    )


def quartiles(rows: list[dict]) -> list[int]:
    order = sorted(range(len(rows)), key=lambda index: (len(rows[index]["rulelist"]), index))
    result = [0] * len(rows)
    for rank, index in enumerate(order):
        result[index] = min(4, (4 * rank) // len(rows) + 1)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-task", required=True)
    parser.add_argument("--target-task", required=True)
    parser.add_argument("--copies", type=int, default=3)
    parser.add_argument("--complex-boost", type=int, default=2)
    parser.add_argument("--seed", type=int, default=273567)
    args = parser.parse_args()
    if args.copies < 1 or args.complex_boost < 1:
        parser.error("--copies and --complex-boost must be positive")

    source = DATA / args.source_task
    target = DATA / args.target_task
    if target.exists():
        raise FileExistsError(f"refusing to overwrite {target}")
    proof = load_pickle(source / "train.pkl")
    plain = json.loads((source / "train_t5_plain_format.json").read_text())
    if not proof or len(proof) != len(plain):
        raise RuntimeError("source proof/plain training rows are empty or misaligned")
    source_rows = len(proof)
    target_rows = source_rows * args.copies
    source_quartiles = quartiles(proof)
    complex_flags = [complex_signature(row) for row in plain]
    weighted_pool = [
        index
        for index in range(source_rows)
        for _ in range(source_quartiles[index] * (args.complex_boost if complex_flags[index] else 1))
    ]
    rng = random.Random(args.seed)
    additions: list[int] = []
    while len(additions) < target_rows - source_rows:
        cycle = weighted_pool.copy()
        rng.shuffle(cycle)
        additions.extend(cycle[: target_rows - source_rows - len(additions)])
    indices = list(range(source_rows)) + additions
    selected_proof = [proof[index] for index in indices]
    selected_plain = [plain[index] for index in indices]

    target.mkdir(parents=True)
    try:
        dump_pickle(selected_proof, target / "train.pkl")
        dump_pickle([], target / "valid.pkl")
        dump_pickle([], target / "test.pkl")
        for split, rows in (("train", selected_proof), ("valid", []), ("test", [])):
            (target / f"{split}.json").write_text(
                json.dumps(rows, indent=2, ensure_ascii=False) + "\n"
            )
        for name, rows in (
            ("train_t5_plain_format.json", selected_plain),
            ("valid_t5_plain_format.json", []),
            ("test_t5_plain_format.json", []),
        ):
            (target / name).write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n")
        for artifact in ARTIFACTS:
            shutil.copy2(source / artifact, target / artifact)
        config = json.loads((source / "config.json").read_text())
        config.update(
            {
                "validation": False,
                "train_rows": target_rows,
                "valid_rows": 0,
                "test_rows": 0,
                "length_repair_parent": args.source_task,
                "length_repair_copies": args.copies,
                "length_repair_complex_boost": args.complex_boost,
                "data_revision": "java-expansion-train-only-length-repair-v1",
            }
        )
        for key in ("plain_loader", "proof_loader"):
            if key in config:
                config[key] = config[key].replace(args.source_task, args.target_task)
        (target / "config.json").write_text(json.dumps(config, indent=2) + "\n")
        occurrence_counts = [0] * source_rows
        for index in indices:
            occurrence_counts[index] += 1
        manifest = {
            "task": args.target_task,
            "source_task": args.source_task,
            "policy": (
                "retain every source training row once, then deterministically replay only "
                "source training rows with weights equal to IR-length quartile times a fixed "
                "complex-signature boost; validation and test are empty"
            ),
            "seed": args.seed,
            "copies": args.copies,
            "complex_signature_boost": args.complex_boost,
            "unique_training_rows": source_rows,
            "effective_training_rows": target_rows,
            "validation_rows": 0,
            "test_rows": 0,
            "selection_uses_test_rows": False,
            "selection_uses_model_outputs": False,
            "selection_uses_execution_results": False,
            "quartile_rows": {
                str(value): sum(item == value for item in source_quartiles)
                for value in range(1, 5)
            },
            "complex_signature_rows": sum(complex_flags),
            "occurrences_minimum": min(occurrence_counts),
            "occurrences_median": sorted(occurrence_counts)[source_rows // 2],
            "occurrences_maximum": max(occurrence_counts),
            "proof_train_sha256": sha256(target / "train.pkl"),
            "plain_train_sha256": sha256(target / "train_t5_plain_format.json"),
            "artifact_sha256": {name: sha256(target / name) for name in ARTIFACTS},
        }
        (target / "length_repair_manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n"
        )
        print(json.dumps(manifest, indent=2))
    except Exception:
        shutil.rmtree(target)
        raise


if __name__ == "__main__":
    main()
