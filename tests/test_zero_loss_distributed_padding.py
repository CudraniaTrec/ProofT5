import json
import pickle
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import Dataset
from run import Dotdict, partition_data_rows


def assert_exact_real_row_partition(shards, expected_rows, expected_padding):
    real_ids = []
    padding_rows = []
    for shard in shards:
        for row in shard:
            if row.get("_distributed_zero_loss_padding", False):
                padding_rows.append(row)
            else:
                real_ids.append(row["row_id"])
    assert sorted(real_ids) == list(range(expected_rows))
    assert len(real_ids) == len(set(real_ids)) == expected_rows
    assert len(padding_rows) == expected_padding


def main():
    sufu_rows = [{"row_id": row_id} for row_id in range(232)]
    sufu_shards, sufu_original_lengths, sufu_padding_counts = partition_data_rows(
        sufu_rows,
        process_num=8,
        add_zero_loss_padding=True,
    )
    assert sufu_original_lengths == [29] * 8
    assert sufu_padding_counts == [0] * 8
    assert [len(shard) for shard in sufu_shards] == [29] * 8

    complete_sufu_rows = [{"row_id": row_id} for row_id in range(281)]
    complete_sufu_shards, complete_sufu_original, complete_sufu_padding = (
        partition_data_rows(
            complete_sufu_rows,
            process_num=8,
            add_zero_loss_padding=True,
        )
    )
    assert complete_sufu_original == [35, 35, 35, 35, 35, 35, 35, 36]
    assert complete_sufu_padding == [1, 1, 1, 1, 1, 1, 1, 0]
    assert [len(shard) for shard in complete_sufu_shards] == [36] * 8
    assert_exact_real_row_partition(complete_sufu_shards, 281, 7)

    complete_java_rows = [{"row_id": row_id} for row_id in range(706)]
    complete_java_shards, complete_java_original, complete_java_padding = (
        partition_data_rows(
            complete_java_rows,
            process_num=8,
            add_zero_loss_padding=True,
        )
    )
    assert complete_java_original == [88, 88, 88, 88, 88, 88, 89, 89]
    assert complete_java_padding == [1, 1, 1, 1, 1, 1, 0, 0]
    assert [len(shard) for shard in complete_java_shards] == [89] * 8
    assert_exact_real_row_partition(complete_java_shards, 706, 6)

    synthetic_rows = [{"row_id": row_id} for row_id in range(541)]
    shards, original_lengths, padding_counts = partition_data_rows(
        synthetic_rows,
        process_num=8,
        add_zero_loss_padding=True,
    )
    assert original_lengths == [67, 67, 67, 68, 68, 68, 68, 68]
    assert padding_counts == [1, 1, 1, 0, 0, 0, 0, 0]
    assert [len(shard) for shard in shards] == [68] * 8

    assert_exact_real_row_partition(shards, 541, 3)

    task_dir = Path(
        "Utils/data/mbjpcoqview_t5gemma2_2b_corrected_from_java30_prefixpadfix_b1_20260718"
    )
    config = Dotdict(json.loads((task_dir / "config.json").read_text()))
    config.mask_id = 0
    Dataset.args = config
    Dataset.PAD_token = 0
    with (task_dir / "train.pkl").open("rb") as handle:
        real_row = pickle.load(handle)[0]

    normal_batch = Dataset.rs_collate_fn_cutprefix([real_row])
    assert "distributed_zero_loss_padding" not in normal_batch
    assert int(normal_batch["res"].ne(0).sum()) > 0

    padding_row = dict(real_row)
    padding_row["_distributed_zero_loss_padding"] = True
    padding_batch = Dataset.rs_collate_fn_cutprefix([padding_row])
    assert padding_batch["distributed_zero_loss_padding"].tolist() == [True]
    assert int(padding_batch["res"].ne(0).sum()) == 0
    assert int(padding_batch["distributed_zero_loss_padding_res"].ne(0).sum()) > 0
    assert padding_batch["coqview"].ndim == 3
    assert padding_batch["coqview"].shape[1] == normal_batch["coqview"].shape[1]
    assert padding_batch["prefix"].shape == normal_batch["prefix"].shape
    assert padding_batch["nl"].shape == normal_batch["nl"].shape

    print(
        {
            "original_lengths": original_lengths,
            "padded_lengths": [len(shard) for shard in shards],
            "padding_counts": padding_counts,
            "padding_active_targets": int(padding_batch["res"].ne(0).sum()),
            "padding_coqview_shape": tuple(padding_batch["coqview"].shape),
            "sufu_original_lengths": sufu_original_lengths,
            "sufu_padding_counts": sufu_padding_counts,
            "complete_java_original_lengths": complete_java_original,
            "complete_java_padding_counts": complete_java_padding,
            "complete_sufu_original_lengths": complete_sufu_original,
            "complete_sufu_padding_counts": complete_sufu_padding,
        }
    )


if __name__ == "__main__":
    main()
