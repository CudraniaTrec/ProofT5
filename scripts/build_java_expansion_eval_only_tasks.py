#!/usr/bin/env python3
"""Create immutable test-only ProofT5 tasks from frozen Java expansions.

The resulting tasks preserve the exact test rows and tokenizer/rule artifacts,
but expose empty train/validation splits.  They are intended as inputs to the
CoqView context builder, so building evaluation context can never accidentally
include training rows.
"""

import argparse
import hashlib
import json
import pickle
import shutil
from pathlib import Path


ARTIFACTS = ("rules.pkl", "rules.json", "tokenizer.pkl", "coq_tokenizer.pkl")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def dump_pickle(value, path: Path) -> None:
    with path.open("wb") as handle:
        pickle.dump(value, handle)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-task", required=True)
    parser.add_argument("--target-task", required=True)
    parser.add_argument("--data-root", default="Utils/data")
    args = parser.parse_args()

    root = Path(args.data_root)
    source = root / args.source_task
    target = root / args.target_task
    if not source.is_dir():
        raise FileNotFoundError(source)
    if target.exists():
        raise FileExistsError(f"Refusing to overwrite target task: {target}")

    with (source / "test.pkl").open("rb") as handle:
        test_rows = pickle.load(handle)
    if not test_rows:
        raise RuntimeError("source test split is empty")
    with (source / "test.json").open() as handle:
        test_json = json.load(handle)
    if len(test_json) != len(test_rows):
        raise RuntimeError("test.pkl and test.json row counts differ")

    target.mkdir(parents=True)
    try:
        dump_pickle([], target / "train.pkl")
        dump_pickle([], target / "valid.pkl")
        # Preserve the frozen benchmark artifact byte-for-byte.  Re-pickling
        # an equivalent object can change memoization/opcode layout.
        shutil.copy2(source / "test.pkl", target / "test.pkl")
        (target / "train.json").write_text("[]\n")
        (target / "valid.json").write_text("[]\n")
        (target / "test.json").write_text(json.dumps(test_json, indent=2) + "\n")
        for name in ARTIFACTS:
            shutil.copy2(source / name, target / name)

        config = json.loads((source / "config.json").read_text())
        config.update(
            {
                "validation": False,
                "evaluation_only": True,
                "contains_debug_split": False,
                "train_rows": 0,
                "valid_rows": 0,
                "test_rows": len(test_rows),
                "data_revision": "frozen-java-expansion-test-only-v1",
                "source_task": args.source_task,
            }
        )
        (target / "config.json").write_text(json.dumps(config, indent=2) + "\n")
        manifest = {
            "target_task": args.target_task,
            "source_task": args.source_task,
            "train_rows": 0,
            "validation_rows": 0,
            "test_rows": len(test_rows),
            "source_test_pickle_sha256": sha256(source / "test.pkl"),
            "target_test_pickle_sha256": sha256(target / "test.pkl"),
            "artifact_sha256": {name: sha256(target / name) for name in ARTIFACTS},
        }
        if manifest["source_test_pickle_sha256"] != manifest["target_test_pickle_sha256"]:
            raise RuntimeError("test pickle changed while creating evaluation-only task")
        (target / "evaluation_only_manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n"
        )
    except Exception:
        shutil.rmtree(target)
        raise

    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
