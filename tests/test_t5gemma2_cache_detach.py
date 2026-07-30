import os
import sys

import torch
from transformers.cache_utils import DynamicCache

sys.path.insert(0, os.getcwd())

from ModelT5Gemma2 import _detach_dynamic_cache


def main():
    prefix_len = 600
    sliding_window = 512
    keys = torch.randn(1, 1, prefix_len, 4, requires_grad=True)
    values = torch.randn(1, 1, prefix_len, 4, requires_grad=True)
    cache = DynamicCache(
        [(keys, values, torch.tensor([sliding_window], dtype=torch.long))]
    )
    layer = cache.layers[0]
    assert layer.get_seq_length() == prefix_len
    assert layer.keys.shape[-2] == sliding_window - 1

    detached = _detach_dynamic_cache(cache)
    assert detached is not cache
    detached_layer = detached.layers[0]
    assert layer.get_seq_length() == prefix_len
    assert detached_layer.get_seq_length() == prefix_len
    assert detached_layer.keys.shape[-2] == sliding_window - 1
    assert layer.keys.requires_grad
    assert not detached_layer.keys.requires_grad
    assert not detached_layer.values.requires_grad

    next_keys = torch.randn(1, 1, 1, 4)
    next_values = torch.randn(1, 1, 1, 4)
    detached_layer.update(next_keys, next_values)
    assert detached_layer.get_seq_length() == prefix_len + 1
    print(
        {
            "prefix_len": prefix_len,
            "stored_kv_len": detached_layer.keys.shape[-2],
            "cumulative_len_after_next_token": detached_layer.get_seq_length(),
        }
    )


if __name__ == "__main__":
    main()
