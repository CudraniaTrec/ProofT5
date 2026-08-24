#!/usr/bin/env python3
"""Build an auditable no-validation source task for a later CoqView stage.

The resulting task has one complete training split and one frozen benchmark
test split.  It deliberately has no ``debug.pkl``: every supplied additional
training row becomes an ordinary member of ``train.pkl``.
"""

import argparse
import hashlib
import json
import pickle
import shutil
from pathlib import Path


COPIED_ARTIFACTS = (
    "rules.pkl",
    "rules.json",
    "tokenizer.pkl",
    "coq_tokenizer.pkl",
    "groundvalid.txt",
)


def load_pickle(path):
    with path.open("rb") as handle:
        return pickle.load(handle)


def dump_pickle(value, path):
    with path.open("wb") as handle:
        pickle.dump(value, handle)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fingerprint_artifacts(data_root, task):
    task_dir = data_root / task
    fingerprints = {}
    for name in COPIED_ARTIFACTS:
        path = task_dir / name
        if path.exists():
            fingerprints[name] = sha256(path)
    return fingerprints


def strip_additional_row_markers(row):
    copied = dict(row)
    for key in (
        "debug_overlap",
        "debug_source_index",
        "debug_source_split",
        "split",
    ):
        copied.pop(key, None)
    return copied


def max_lengths(rows):
    if not rows:
        return {"CodeLen": 0, "max_code_len": 0, "NlLen": 0}
    code_lengths = [len(row["rulelist"]) - 2 for row in rows]
    suffix_lengths = [
        len(row["rulelist"][1:-1]) - len(row.get("prefix", [])) for row in rows
    ]
    nl_lengths = [len(row["nl"]) for row in rows]
    return {
        "CodeLen": max(code_lengths),
        "max_code_len": max(suffix_lengths),
        "NlLen": max(nl_lengths),
    }


def build_task(data_root, train_task, eval_task, target_task):
    train_dir = data_root / train_task
    eval_dir = data_root / eval_task
    target_dir = data_root / target_task
    if target_dir.exists():
        raise FileExistsError(f"Refusing to overwrite existing task: {target_dir}")

    train_fingerprints = fingerprint_artifacts(data_root, train_task)
    eval_fingerprints = fingerprint_artifacts(data_root, eval_task)
    if train_fingerprints != eval_fingerprints:
        raise RuntimeError(
            "Training and evaluation tasks do not share exactly the same "
            f"token/rule artifacts: {train_fingerprints} != {eval_fingerprints}"
        )

    main_train = load_pickle(train_dir / "train.pkl")
    additional_train = load_pickle(train_dir / "debug.pkl")
    benchmark_test = load_pickle(eval_dir / "test.pkl")
    complete_train = list(main_train) + [
        strip_additional_row_markers(row) for row in additional_train
    ]
    if not complete_train or not benchmark_test:
        raise RuntimeError("Complete training and benchmark test splits must both be non-empty")

    all_lengths = max_lengths(complete_train + benchmark_test)
    config = json.loads((train_dir / "config.json").read_text())
    config.update(
        {
            "CodeLen": all_lengths["CodeLen"],
            "max_code_len": all_lengths["max_code_len"],
            "NlLen": max(int(config.get("NlLen", 0)), all_lengths["NlLen"]),
            "validation": False,
            "evaluation_only": False,
            "contains_debug_split": False,
            "complete_training_rows": len(complete_train),
            "benchmark_test_rows": len(benchmark_test),
            "data_revision": "complete-training-with-frozen-paper-test-v1",
        }
    )
    for key in ("debug_split", "debug_rows"):
        config.pop(key, None)

    manifest = {
        "target_task": target_task,
        "training_task": train_task,
        "evaluation_task": eval_task,
        "training_rows": len(complete_train),
        "main_training_rows": len(main_train),
        "additional_training_rows": len(additional_train),
        "benchmark_test_rows": len(benchmark_test),
        "validation_rows": 0,
        "artifact_sha256": train_fingerprints,
        "max_lengths": all_lengths,
        "data_revision": config["data_revision"],
    }

    target_dir.mkdir(parents=True)
    try:
        dump_pickle(complete_train, target_dir / "train.pkl")
        dump_pickle([], target_dir / "valid.pkl")
        dump_pickle(benchmark_test, target_dir / "test.pkl")
        (target_dir / "config.json").write_text(json.dumps(config, indent=2) + "\n")
        (target_dir / "complete_training_manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n"
        )
        for name in COPIED_ARTIFACTS:
            source = train_dir / name
            if source.exists():
                shutil.copy2(source, target_dir / name)
    except Exception:
        shutil.rmtree(target_dir)
        raise
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-task", required=True)
    parser.add_argument("--eval-task", required=True)
    parser.add_argument("--target-task", required=True)
    parser.add_argument("--data-root", default="Utils/data")
    args = parser.parse_args()
    manifest = build_task(
        Path(args.data_root), args.train_task, args.eval_task, args.target_task
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
