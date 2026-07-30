import json
import os
import sys
from pathlib import Path

import torch
import torch.distributed as dist

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from run import all_reduce_gradients


def main():
    dist.init_process_group(backend="gloo")
    rank = dist.get_rank()
    world_size = dist.get_world_size()
    assert world_size == 8

    torch.manual_seed(20260718)
    model = torch.nn.Linear(4, 3, bias=True)
    initial_state = {name: value.detach().clone() for name, value in model.state_dict().items()}

    is_padding = rank < 3
    local_active = torch.tensor([0 if is_padding else 1], dtype=torch.long)
    dist.all_reduce(local_active, op=dist.ReduceOp.SUM)
    global_active = int(local_active.item())
    assert global_active == 5

    if is_padding:
        logits = model(torch.zeros(1, 4))
        loss = logits.sum() * 0.0
    else:
        sample_id = rank - 3
        features = torch.tensor(
            [[sample_id + 1.0, sample_id * 0.5, 1.0 - sample_id, -0.25 * sample_id]]
        )
        target = torch.tensor([sample_id % 3], dtype=torch.long)
        raw_loss = torch.nn.functional.cross_entropy(model(features), target, reduction="sum")
        loss = raw_loss * world_size / global_active
    loss.backward()
    all_reduce_gradients(model, world_size)

    reference = torch.nn.Linear(4, 3, bias=True)
    reference.load_state_dict(initial_state)
    reference_features = []
    reference_targets = []
    for sample_id in range(5):
        reference_features.append(
            [sample_id + 1.0, sample_id * 0.5, 1.0 - sample_id, -0.25 * sample_id]
        )
        reference_targets.append(sample_id % 3)
    reference_loss = torch.nn.functional.cross_entropy(
        reference(torch.tensor(reference_features)),
        torch.tensor(reference_targets),
        reduction="mean",
    )
    reference_loss.backward()

    max_gradient_difference = 0.0
    for parameter, reference_parameter in zip(model.parameters(), reference.parameters()):
        max_gradient_difference = max(
            max_gradient_difference,
            float((parameter.grad - reference_parameter.grad).abs().max()),
        )
    assert max_gradient_difference < 1e-6, max_gradient_difference

    if rank == 0:
        print(
            json.dumps(
                {
                    "world_size": world_size,
                    "real_rows": global_active,
                    "zero_loss_padding_rows": world_size - global_active,
                    "max_gradient_difference": max_gradient_difference,
                },
                sort_keys=True,
            )
        )
    dist.destroy_process_group()


if __name__ == "__main__":
    main()
