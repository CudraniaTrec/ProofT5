import pytest

from scripts.select_plain_checkpoint_from_training_log import (
    parse_complete_training_log,
)


def test_plain_training_log_preserves_high_precision_and_accounting():
    text = """
run epoch 0: active_target_tokens=101 batches=3
run epoch 0: loss=0.00000123456789
run epoch 1: active_target_tokens=101 batches=3
run epoch 1: loss=0.00000123456701
"""
    losses, accounting = parse_complete_training_log(text, expected_passes=2)
    assert losses == [(0, 0.00000123456789), (1, 0.00000123456701)]
    assert accounting == [(0, 101, 3), (1, 101, 3)]


def test_plain_training_log_rejects_missing_accounting():
    with pytest.raises(RuntimeError, match="token accounting"):
        parse_complete_training_log("run epoch 0: loss=0.1", expected_passes=1)


def test_plain_training_log_rejects_token_count_drift():
    text = """
run epoch 0: active_target_tokens=101 batches=3
run epoch 0: loss=0.2
run epoch 1: active_target_tokens=100 batches=3
run epoch 1: loss=0.1
"""
    with pytest.raises(RuntimeError, match="changed across epochs"):
        parse_complete_training_log(text, expected_passes=2)
