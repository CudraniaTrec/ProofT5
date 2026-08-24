#!/usr/bin/env python3
"""Build an immutable evaluation-only task from selected rows of a source split."""

import argparse
import hashlib
import json
import pickle
import shutil
from pathlib import Path


ARTIFACTS = ("rules.pkl", "rules.json", "tokenizer.pkl", "coq_tokenizer.pkl")


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_pickle(path):
    with path.open("rb") as handle:
        return pickle.load(handle)


def dump_pickle(value, path):
    with path.open("wb") as handle:
        pickle.dump(value, handle)


def row_digest(row):
    return hashlib.sha256(pickle.dumps(row, protocol=4)).hexdigest()


def build_task(
    data_root,
    source_task,
    source_split,
    benchmark,
    target_task,
    explicit_indices=None,
    parallel_plain_json=None,
):
    source_dir = data_root / source_task
    target_dir = data_root / target_task
    if not source_dir.is_dir():
        raise FileNotFoundError(f"Source task is absent: {source_dir}")
    if target_dir.exists():
        raise FileExistsError(f"Refusing to overwrite target task: {target_dir}")

    source_pickle = source_dir / f"{source_split}.pkl"
    pickle_rows = load_pickle(source_pickle)
    source_json = source_dir / f"{source_split}.json"
    json_rows = (
        json.loads(source_json.read_text())
        if source_json.exists()
        else pickle_rows
    )
    if len(pickle_rows) != len(json_rows):
        raise RuntimeError("Source JSON and PKL lengths differ")

    indices = (
        list(explicit_indices)
        if explicit_indices is not None else
        [
            index for index, row in enumerate(json_rows)
            if row.get("benchmark") == benchmark
        ]
    )
    invalid = [index for index in indices if index < 0 or index >= len(json_rows)]
    if invalid or len(indices) != len(set(indices)):
        raise RuntimeError(f"invalid or duplicate explicit indices: {invalid or indices}")
    if not indices:
        raise RuntimeError(f"No rows selected for benchmark={benchmark!r}")
    selected_pickle = [pickle_rows[index] for index in indices]
    selected_json = [json_rows[index] for index in indices]
    if selected_pickle != selected_json:
        raise RuntimeError("Selected JSON rows are not exactly equal to PKL rows")

    selected_plain = None
    plain_source_sha256 = None
    if parallel_plain_json is not None:
        parallel_plain_json = Path(parallel_plain_json)
        plain_rows = json.loads(parallel_plain_json.read_text())
        if len(plain_rows) < len(json_rows):
            raise RuntimeError(
                "Parallel plain JSON has fewer rows than the proof source split"
            )
        selected_plain = []
        for index in indices:
            plain_row = dict(plain_rows[index])
            proof_benchmark = json_rows[index].get("benchmark")
            plain_benchmark = plain_row.get("benchmark")
            if (
                proof_benchmark is not None
                and plain_benchmark is not None
                and proof_benchmark != plain_benchmark
            ):
                raise RuntimeError(
                    f"proof/plain benchmark mismatch at source index {index}: "
                    f"{proof_benchmark!r} != {plain_benchmark!r}"
                )
            plain_row["type"] = "test"
            plain_row["split"] = "test"
            selected_plain.append(plain_row)
        plain_source_sha256 = sha256(parallel_plain_json)

    config = json.loads((source_dir / "config.json").read_text())
    config.update(
        {
            "validation": False,
            "evaluation_only": True,
            "contains_debug_split": False,
            "evaluation_source_task": source_task,
            "evaluation_source_split": source_split,
            "evaluation_benchmark": benchmark,
            "evaluation_source_indices": indices,
            "evaluation_rows": len(indices),
        }
    )
    for key in ("debug_split", "debug_rows", "complete_training_rows"):
        config.pop(key, None)

    artifact_hashes = {}
    for name in ARTIFACTS:
        path = source_dir / name
        if not path.exists():
            raise FileNotFoundError(f"Source artifact is absent: {path}")
        artifact_hashes[name] = sha256(path)
    manifest = {
        "target_task": target_task,
        "source_task": source_task,
        "source_split": source_split,
        "benchmark": benchmark,
        "source_rows": len(pickle_rows),
        "selected_rows": len(indices),
        "source_indices": indices,
        "source_pickle_sha256": sha256(source_pickle),
        "row_sha256": [row_digest(row) for row in selected_pickle],
        "parallel_plain_json": (
            str(parallel_plain_json) if parallel_plain_json is not None else None
        ),
        "parallel_plain_json_sha256": plain_source_sha256,
        "artifact_sha256": artifact_hashes,
    }

    target_dir.mkdir(parents=True)
    try:
        for split, rows in (("train", []), ("valid", []), ("test", selected_pickle)):
            dump_pickle(rows, target_dir / f"{split}.pkl")
        for split, rows in (("train", []), ("valid", []), ("test", selected_json)):
            (target_dir / f"{split}.json").write_text(json.dumps(rows, indent=2) + "\n")
        if selected_plain is not None:
            (target_dir / "test_t5_plain_format.json").write_text(
                json.dumps(selected_plain, indent=2) + "\n"
            )
        (target_dir / "config.json").write_text(json.dumps(config, indent=2) + "\n")
        (target_dir / "evaluation_subset_manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n"
        )
        for name in ARTIFACTS:
            shutil.copy2(source_dir / name, target_dir / name)
    except Exception:
        shutil.rmtree(target_dir)
        raise
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-task", required=True)
    parser.add_argument("--source-split", choices=("train", "valid", "test"), required=True)
    parser.add_argument("--benchmark", default="")
    parser.add_argument("--indices", default="")
    parser.add_argument("--target-task", required=True)
    parser.add_argument("--parallel-plain-json")
    parser.add_argument("--data-root", default="Utils/data")
    args = parser.parse_args()
    explicit_indices = None
    if args.indices:
        explicit_indices = [int(value) for value in args.indices.split(",") if value.strip()]
    if (explicit_indices is None) == (not args.benchmark):
        parser.error("provide exactly one of --benchmark or --indices")
    manifest = build_task(
        Path(args.data_root), args.source_task, args.source_split,
        args.benchmark or "explicit_indices", args.target_task, explicit_indices,
        args.parallel_plain_json,
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
