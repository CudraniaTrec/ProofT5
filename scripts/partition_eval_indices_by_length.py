#!/usr/bin/env python3
"""Create deterministic longest-processing-time eval shards from a task pickle."""

from __future__ import annotations

import argparse
import hashlib
import json
import pickle
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def partition(
    lengths: list[int],
    shard_count: int,
    indices: list[int] | None = None,
) -> list[list[int]]:
    if shard_count <= 0:
        raise ValueError("shard_count must be positive")
    if not lengths:
        raise ValueError("cannot partition an empty split")
    selected = list(range(len(lengths))) if indices is None else list(indices)
    if not selected:
        raise ValueError("cannot partition an empty index subset")
    if len(selected) != len(set(selected)):
        raise ValueError("indices contain duplicates")
    invalid = [index for index in selected if index < 0 or index >= len(lengths)]
    if invalid:
        raise ValueError(f"indices out of range: {invalid}")
    if shard_count > len(selected):
        raise ValueError("shard_count cannot exceed the row count")
    shards: list[list[int]] = [[] for _ in range(shard_count)]
    loads = [0] * shard_count
    for index in sorted(selected, key=lambda idx: (-lengths[idx], idx)):
        target = min(range(shard_count), key=lambda shard: (loads[shard], shard))
        shards[target].append(index)
        loads[target] += lengths[index]
    for shard in shards:
        shard.sort()
    return shards


def build_manifest(
    task_dir: Path,
    split: str,
    shard_count: int,
    length_key: str,
    indices: list[int] | None = None,
) -> dict:
    pickle_path = task_dir / f"{split}.pkl"
    with pickle_path.open("rb") as handle:
        rows = pickle.load(handle)
    lengths = []
    for index, row in enumerate(rows):
        if length_key not in row:
            raise KeyError(f"row {index} lacks length key {length_key!r}")
        value = row[length_key]
        if not hasattr(value, "__len__"):
            raise TypeError(f"row {index} field {length_key!r} has no length")
        lengths.append(len(value))
    selected = list(range(len(rows))) if indices is None else list(indices)
    shards = partition(lengths, shard_count, selected)
    return {
        "schema_version": 1,
        "task_dir": str(task_dir.resolve()),
        "split": split,
        "split_pickle_sha256": sha256(pickle_path),
        "source_row_count": len(rows),
        "row_count": len(selected),
        "selected_indices": selected,
        "length_key": length_key,
        "shard_count": shard_count,
        "shards": [
            {
                "shard": shard_id,
                "indices": indices,
                "indices_csv": ",".join(map(str, indices)),
                "rows": len(indices),
                "length_sum": sum(lengths[index] for index in indices),
                "length_max": max(lengths[index] for index in indices),
            }
            for shard_id, indices in enumerate(shards)
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--split", default="test")
    parser.add_argument("--shards", required=True, type=int)
    parser.add_argument("--length-key", default="tokens")
    parser.add_argument(
        "--indices",
        default="",
        help="optional comma-separated source indices to repartition",
    )
    parser.add_argument("--json-out", required=True, type=Path)
    args = parser.parse_args()
    if args.json_out.exists():
        raise FileExistsError(f"refusing to overwrite {args.json_out}")
    indices = (
        [int(value) for value in args.indices.split(",") if value.strip()]
        if args.indices else None
    )
    manifest = build_manifest(
        args.task_dir, args.split, args.shards, args.length_key, indices
    )
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"json_out": str(args.json_out), "loads": [s["length_sum"] for s in manifest["shards"]]}))


if __name__ == "__main__":
    main()
