import importlib.util
import pickle
from pathlib import Path

import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "audit_complete_coqview_training.py"
)
SPEC = importlib.util.spec_from_file_location("training_audit", MODULE_PATH)
training_audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(training_audit)


def test_runtime_shards_match_source_multiset(tmp_path):
    source = [{"row_id": row_id, "tokens": [row_id]} for row_id in range(5)]
    train_pickle = tmp_path / "train.pkl"
    train_pickle.write_bytes(pickle.dumps(source))
    shards, original, padding = [], [1, 1, 1, 2], [1, 1, 1, 0]
    start = 0
    for rank, (real_count, pad_count) in enumerate(zip(original, padding)):
        shard = list(source[start : start + real_count])
        start += real_count
        if pad_count:
            pad = dict(shard[-1])
            pad["_distributed_zero_loss_padding"] = True
            shard.append(pad)
        shards.append(shard)
        (tmp_path / f"data_train{rank}.pkl").write_bytes(pickle.dumps(shard))

    result = training_audit.audit_runtime_shards(
        train_pickle, tmp_path, 4, original, padding
    )

    assert result["content_multiset_exact_match"] is True
    assert result["runtime_real_rows"] == 5
    assert result["runtime_shard_lengths"] == [2, 2, 2, 2]
    assert result["runtime_padding_counts"] == [1, 1, 1, 0]


def test_rank_loss_accounting_reconstructs_global_loss():
    record = {
        "loss": 0.3,
        "coqview_global_active_targets": 10,
        "coqview_rank_active_targets": [4, 6],
        "coqview_rank_loss_sums": [1.2, 1.8],
    }
    assert training_audit.validate_rank_loss_accounting(record, 2) == pytest.approx(0.3)

    record["loss"] = 0.31
    with pytest.raises(RuntimeError, match="reconstructed global loss"):
        training_audit.validate_rank_loss_accounting(record, 2)

    record["loss"] = 0.3
    record["coqview_rank_active_targets"] = [3, 6]
    with pytest.raises(RuntimeError, match="rank active targets"):
        training_audit.validate_rank_loss_accounting(record, 2)
