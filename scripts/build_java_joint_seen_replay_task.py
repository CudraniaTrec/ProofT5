#!/usr/bin/env python3
"""Build a labelled HumanEval seen-replay continuation task.

This builder is intentionally diagnostic.  It starts from an audited joint
MBJP/HumanEval/GFG training-only task and adds deterministic replay copies of
the first 33 rows from the existing HumanEval seen/unseen diagnostic.  The
result has empty validation and test splits.  Its manifest explicitly records
that evaluation on the 66-row diagnostic is contaminated and must not be
reported as held-out generalization.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pickle
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path):
    return json.loads(path.read_text())


def dump_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def load_pickle(path: Path):
    with path.open("rb") as handle:
        return pickle.load(handle)


def dump_pickle(path: Path, value) -> None:
    with path.open("wb") as handle:
        pickle.dump(value, handle)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-task", required=True)
    parser.add_argument("--diagnostic-task", required=True)
    parser.add_argument("--output-task", required=True)
    parser.add_argument("--seen-rows", type=int, default=33)
    parser.add_argument("--replay-copies", type=int, default=4)
    args = parser.parse_args()

    if args.seen_rows <= 0 or args.replay_copies <= 0:
        raise ValueError("seen-rows and replay-copies must be positive")

    data_root = ROOT / "Utils" / "data"
    base = data_root / args.base_task
    diagnostic = data_root / args.diagnostic_task
    output = data_root / args.output_task
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")

    required = (
        "train.pkl",
        "train.json",
        "train_t5_plain_format.json",
        "valid.pkl",
        "test.pkl",
        "config.json",
        "rules.pkl",
        "rules.json",
        "tokenizer.pkl",
        "coq_tokenizer.pkl",
    )
    for name in required:
        if not (base / name).is_file():
            raise FileNotFoundError(base / name)
    for name in ("test.pkl", "test.json", "test_t5_plain_format.json"):
        if not (diagnostic / name).is_file():
            raise FileNotFoundError(diagnostic / name)

    base_proof = load_pickle(base / "train.pkl")
    base_json = load_json(base / "train.json")
    base_plain = load_json(base / "train_t5_plain_format.json")
    seen_proof = load_pickle(diagnostic / "test.pkl")[: args.seen_rows]
    seen_json = load_json(diagnostic / "test.json")[: args.seen_rows]
    seen_plain = load_json(diagnostic / "test_t5_plain_format.json")[: args.seen_rows]
    if not (
        len(base_proof) == len(base_json) == len(base_plain)
        and len(seen_proof) == len(seen_json) == len(seen_plain) == args.seen_rows
    ):
        raise RuntimeError("proof/plain row counts are not aligned")

    replay_plain = []
    for _ in range(args.replay_copies):
        for row in seen_plain:
            copied = dict(row)
            copied["type"] = "train"
            copied.pop("debug_overlap", None)
            replay_plain.append(copied)

    shutil.copytree(base, output)
    train_proof = base_proof + seen_proof * args.replay_copies
    train_json = base_json + seen_json * args.replay_copies
    train_plain = base_plain + replay_plain
    dump_pickle(output / "train.pkl", train_proof)
    dump_json(output / "train.json", train_json)
    dump_json(output / "train_t5_plain_format.json", train_plain)

    config = load_json(output / "config.json")
    config.update(
        {
            "train_rows": len(train_proof),
            "valid_rows": 0,
            "test_rows": 0,
            "validation": False,
            "data_revision": "joint-three-source-humaneval-seen-replay-diagnostic-v1",
            "seen_replay_rows": args.seen_rows,
            "seen_replay_copies": args.replay_copies,
            "seen_replay_occurrences": args.seen_rows * args.replay_copies,
        }
    )
    dump_json(output / "config.json", config)

    manifest = {
        "task": args.output_task,
        "base_task": args.base_task,
        "diagnostic_source_task": args.diagnostic_task,
        "role": "training-chain diagnostic only; not a held-out benchmark route",
        "base_train_rows": len(base_proof),
        "seen_replay_unique_rows": args.seen_rows,
        "seen_replay_copies": args.replay_copies,
        "seen_replay_occurrences": args.seen_rows * args.replay_copies,
        "effective_train_rows": len(train_proof),
        "validation_rows": 0,
        "test_rows": 0,
        "ordinary_and_proof_row_counts_match": len(train_proof) == len(train_plain),
        "checkpoint_selection": "complete training loss and training-side execution gates only",
        "reporting_constraint": (
            "Scores on the 66-row seen/unseen HumanEval diagnostic are contaminated; "
            "report seen and unseen membership separately and never label the aggregate held out."
        ),
        "artifact_sha256": {
            name: sha256(output / name)
            for name in (
                "train.pkl",
                "train.json",
                "train_t5_plain_format.json",
                "rules.pkl",
                "tokenizer.pkl",
            )
        },
    }
    dump_json(output / "seen_replay_manifest.json", manifest)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
