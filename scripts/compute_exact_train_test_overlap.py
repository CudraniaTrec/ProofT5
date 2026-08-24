#!/usr/bin/env python3
"""Compute exact complete-row train/test overlap for a frozen task."""

import argparse
import json
import pickle
from pathlib import Path


def overlap_indices(train_rows, test_rows):
    return [
        test_index
        for test_index, test_row in enumerate(test_rows)
        if any(test_row == train_row for train_row in train_rows)
    ]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task_dir", type=Path, required=True)
    parser.add_argument("--expected_train", type=int, required=True)
    parser.add_argument("--expected_test", type=int, required=True)
    parser.add_argument("--expected_overlap", type=int, required=True)
    parser.add_argument("--format", choices=["json", "indices"], default="json")
    args = parser.parse_args()

    train_rows = pickle.loads((args.task_dir / "train.pkl").read_bytes())
    test_rows = pickle.loads((args.task_dir / "test.pkl").read_bytes())
    if len(train_rows) != args.expected_train:
        raise SystemExit(
            f"train rows {len(train_rows)} != expected {args.expected_train}"
        )
    if len(test_rows) != args.expected_test:
        raise SystemExit(
            f"test rows {len(test_rows)} != expected {args.expected_test}"
        )
    indices = overlap_indices(train_rows, test_rows)
    if len(indices) != args.expected_overlap:
        raise SystemExit(
            f"exact overlap {len(indices)} != expected {args.expected_overlap}"
        )
    if args.format == "indices":
        print(",".join(map(str, indices)))
    else:
        print(
            json.dumps(
                {
                    "task_dir": str(args.task_dir),
                    "train_rows": len(train_rows),
                    "test_rows": len(test_rows),
                    "exact_complete_row_overlap": len(indices),
                    "overlap_test_indices": indices,
                },
                indent=2,
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    main()
