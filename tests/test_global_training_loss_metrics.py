import pytest
import torch

import run


def test_global_training_loss_is_weighted_by_active_tokens():
    assert run.aggregate_distributed_token_mean(
        [1.0, 3.0, 100.0], [2, 6, 0]
    ) == pytest.approx(2.5)


def test_global_training_loss_rejects_empty_distributed_batch():
    with pytest.raises(ValueError, match="no active target tokens"):
        run.aggregate_distributed_token_mean([0.0, 0.0], [0, 0])


def test_global_training_loss_rejects_rank_shape_mismatch():
    with pytest.raises(ValueError, match="equal nonzero length"):
        run.aggregate_distributed_token_mean([1.0], [1, 2])


def test_target_count_matches_shifted_non_prefix_forward():
    res = torch.tensor([[10, 11, 12, 0], [20, 21, 0, 0]])
    assert run.count_active_target_tokens(res, mask_id=0, has_prefix=False) == 3


def test_target_count_includes_complete_body_for_cut_prefix_forward():
    body = torch.tensor([[11, 12, 0], [21, 0, 0]])
    assert run.count_active_target_tokens(body, mask_id=0, has_prefix=True) == 3


def test_ddp_backward_scales_local_means_to_global_token_mean():
    counts = [2, 6, 0]
    scales = [
        run.distributed_token_mean_backward_scale(count, sum(counts), len(counts))
        for count in counts
    ]
    # DDP averages rank gradients, so the effective coefficients must equal
    # each rank's fraction of the global target-token count.
    assert [scale / len(counts) for scale in scales] == pytest.approx(
        [count / sum(counts) for count in counts]
    )
