from scripts.partition_eval_indices_by_length import partition


def test_partition_is_complete_deterministic_and_balanced() -> None:
    lengths = [9, 8, 7, 6, 5, 4]
    shards = partition(lengths, 3)
    assert shards == partition(lengths, 3)
    assert sorted(index for shard in shards for index in shard) == list(range(6))
    loads = [sum(lengths[index] for index in shard) for shard in shards]
    assert max(loads) - min(loads) <= max(lengths)


def test_partition_accepts_a_sparse_source_index_subset() -> None:
    lengths = [100, 9, 80, 7, 60, 5]
    selected = [1, 3, 5]
    shards = partition(lengths, 2, selected)

    assert shards == partition(lengths, 2, selected)
    assert sorted(index for shard in shards for index in shard) == selected
    assert all(index in selected for shard in shards for index in shard)
