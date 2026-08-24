#!/usr/bin/env python3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from run import (
    distributed_eval_index_positions,
    distributed_eval_range_slice,
    partition_selected_eval_rows,
    resolve_eval_decode_max_len,
)


def test_arbitrary_eval_indices_are_exact_and_unique_across_shards():
    total = 58
    requested = [0, 10, 19, 26, 32, 48, 52, 57]
    lengths = shard_lengths(total, 8)
    selected = []
    shard_start = 0
    for length in lengths:
        pairs = distributed_eval_index_positions(
            shard_start, length, total, requested
        )
        selected.extend(global_id for _, global_id in pairs)
        for local_position, global_id in pairs:
            assert global_id == shard_start + local_position
        shard_start += length
    assert selected == requested


def test_arbitrary_eval_indices_reject_duplicates_and_out_of_range():
    for requested in ([1, 1], [-1], [58]):
        try:
            distributed_eval_index_positions(0, 58, 58, requested)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid indices accepted: {requested}")


def test_selected_eval_rows_are_balanced_and_keep_global_ids():
    rows = [{"value": index} for index in range(20)]
    shards, id_shards, lengths, padding = partition_selected_eval_rows(
        rows, 4, [1, 3, 7, 9, 12, 16, 18]
    )
    assert lengths == [1, 2, 2, 2]
    assert padding == [0, 0, 0, 0]
    assert id_shards == [[1], [3, 7], [9, 12], [16, 18]]
    assert [[row["value"] for row in shard] for shard in shards] == id_shards


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
    assert resolve_eval_decode_max_len({"eval_max_len": 300, "max_code_len": 227, "CodeLen": 1852}) == 300
    assert resolve_eval_decode_max_len({"eval_max_len": 0, "max_code_len": 227, "CodeLen": 1852}) == 227
    assert resolve_eval_decode_max_len({"eval_max_len": 0, "max_code_len": 0, "CodeLen": 1852}) == 1852
    print({"cases": len(cases), "all_ranges_exact_and_unique": True})


if __name__ == "__main__":
    main()
