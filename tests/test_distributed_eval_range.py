#!/usr/bin/env python3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from run import distributed_eval_range_slice


def shard_lengths(total, ranks):
    size = (total + ranks - 1) // ranks
    lengths = [size] * ranks
    for index in range(size * ranks - total):
        lengths[index] -= 1
    return lengths


def selected_global_rows(total, ranks, start, limit):
    lengths = shard_lengths(total, ranks)
    selected = []
    shard_start = 0
    rank_records = []
    for rank, length in enumerate(lengths):
        local_start, local_end, output_offset = distributed_eval_range_slice(
            shard_start,
            length,
            total,
            start,
            limit,
        )
        rows = list(range(shard_start, shard_start + length))[local_start:local_end]
        if rows:
            assert output_offset == rows[0]
        selected.extend(rows)
        rank_records.append(
            {
                "rank": rank,
                "shard_start": shard_start,
                "shard_length": length,
                "local_slice": [local_start, local_end],
                "global_rows": rows,
            }
        )
        shard_start += length
    expected_end = total if limit <= 0 else min(total, start + limit)
    expected = list(range(min(start, total), expected_end))
    assert selected == expected
    assert len(selected) == len(set(selected))
    return rank_records


def main():
    cases = [
        (67, 8, 0, 0),
        (67, 8, 53, 1),
        (67, 8, 7, 10),
        (67, 8, 66, 10),
        (67, 8, 100, 1),
        (58, 8, 54, 1),
        (541, 8, 0, 0),
        (232, 8, 225, 7),
    ]
    evidence = {}
    for total, ranks, start, limit in cases:
        key = f"n{total}_r{ranks}_start{start}_limit{limit}"
        evidence[key] = selected_global_rows(total, ranks, start, limit)
    print({"cases": len(cases), "all_ranges_exact_and_unique": True})


if __name__ == "__main__":
    main()
