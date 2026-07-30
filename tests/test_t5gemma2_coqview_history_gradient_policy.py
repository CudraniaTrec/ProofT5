#!/usr/bin/env python3
import argparse
import copy
import json
from pathlib import Path
import sys

import torch
import transformers
from transformers import T5Gemma2Config, T5Gemma2ForConditionalGeneration
from transformers.cache_utils import DynamicCache, EncoderDecoderCache

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ModelT5Gemma2 import (
    MyT5Gemma2withCoq1,
    _detach_self_attention_cache,
    _drop_cross_attention_cache,
)


POLICY = "streaming_detached_self_kv"


def tiny_config():
    with open("Utils/models/t5gemma-2-1b-1b/config.json", encoding="utf-8") as handle:
        raw = json.load(handle)

    raw.update(dtype="float32", vocab_size=64, image_token_index=61, eoi_token_index=60)
    common = {
        "dtype": "float32",
        "vocab_size": 64,
        "hidden_size": 32,
        "intermediate_size": 64,
        "num_hidden_layers": 2,
        "num_attention_heads": 4,
        "num_key_value_heads": 2,
        "head_dim": 8,
        "max_position_embeddings": 128,
        "sliding_window": 32,
        "query_pre_attn_scalar": 8,
        "bos_token_id": 2,
        "eos_token_id": 1,
        "pad_token_id": 0,
        "layer_types": ["sliding_attention", "full_attention"],
    }
    raw["decoder"].update(common)
    raw["encoder"]["text_config"].update(common)
    raw["encoder"].update(
        dtype="float32",
        vocab_size=64,
        boi_token_index=59,
        eoi_token_index=60,
        image_token_index=61,
        mm_tokens_per_image=1,
    )
    raw["encoder"]["vision_config"].update(
        dtype="float32",
        hidden_size=32,
        intermediate_size=64,
        num_hidden_layers=1,
        num_attention_heads=4,
        image_size=14,
        patch_size=14,
        num_channels=3,
    )
    return T5Gemma2Config.from_dict(raw)


def sample_inputs():
    return {
        "nl": torch.tensor([[2, 11, 12, 1]]),
        "views": torch.tensor([[[21, 0], [22, 23], [24, 0], [25, 26]]]),
        "prefix": torch.tensor([[2, 30, 31]]),
        "target": torch.tensor([[32, 33, 34, 1]]),
    }


def run_steps(model, config, detach_history, backward_each_step):
    data = sample_inputs()
    cache = EncoderDecoderCache(
        DynamicCache(config=config.decoder),
        DynamicCache(),
    )
    logits = []
    losses = []
    loss_values = []

    for index in range(data["target"].shape[1]):
        encoder_input = torch.cat([data["nl"], data["views"][:, index, :]], dim=-1)
        encoder_mask = encoder_input.ne(0)
        encoder_hidden = model.model.encoder(
            input_ids=encoder_input,
            attention_mask=encoder_mask,
        ).last_hidden_state
        decoder_input = (
            data["prefix"] if index == 0 else data["target"][:, index - 1 : index]
        )
        decoder_output = model.model.decoder(
            input_ids=decoder_input,
            attention_mask=None,
            encoder_hidden_states=encoder_hidden,
            encoder_attention_mask=encoder_mask,
            past_key_values=_drop_cross_attention_cache(cache),
            use_cache=True,
        )
        cache = (
            _detach_self_attention_cache(decoder_output.past_key_values)
            if detach_history
            else decoder_output.past_key_values
        )
        step_logits = model.lm_head(decoder_output.last_hidden_state[:, -1, :])
        step_loss = torch.nn.functional.cross_entropy(step_logits, data["target"][:, index])
        logits.append(step_logits.detach())
        loss_values.append(float(step_loss.detach()))
        if backward_each_step:
            step_loss.backward()
        else:
            losses.append(step_loss)

    if not backward_each_step:
        torch.stack(losses).sum().backward()
    return logits, loss_values


def gradients(model):
    return {
        name: parameter.grad.detach().clone()
        for name, parameter in model.named_parameters()
        if parameter.grad is not None
    }


def wrap_tiny_model(model):
    wrapped = MyT5Gemma2withCoq1.__new__(MyT5Gemma2withCoq1)
    torch.nn.Module.__init__(wrapped)
    wrapped.seq2seq = copy.deepcopy(model)
    wrapped.model = wrapped.seq2seq.model
    wrapped.lm_head = wrapped.seq2seq.lm_head
    wrapped.mask_id = 0
    wrapped.vocab_size = wrapped.seq2seq.config.vocab_size
    return wrapped.eval()


def public_training_losses(model):
    data = sample_inputs()
    with torch.no_grad():
        return [
            float(loss)
            for loss in model.coqview_step_losses(
                data["nl"],
                data["target"],
                data["views"],
                data["prefix"],
                total_steps=data["target"].shape[1],
                loss_reduction="sum",
                history_gradient_policy=POLICY,
            )
        ]


def public_inference_losses(model):
    data = sample_inputs()
    encoded_nl, nl_mask = model.encode_nl(data["nl"])
    past_key_values = None
    losses = []
    with torch.no_grad():
        for index in range(data["target"].shape[1]):
            decoder_input = (
                data["prefix"]
                if index == 0
                else data["target"][:, index - 1 : index]
            )
            logits, past_key_values = model.test_forward_logits(
                encoded_nl,
                nl_mask,
                decoder_input,
                data["views"][:, index : index + 1, :],
                past_key_values=past_key_values,
            )
            losses.append(
                float(
                    torch.nn.functional.cross_entropy(
                        logits[:, -1, :], data["target"][:, index], reduction="sum"
                    )
                )
            )
    return losses


def max_logit_difference(left, right):
    return max(float((a - b).abs().max()) for a, b in zip(left, right))


def max_gradient_difference(left, right):
    shared = sorted(set(left) & set(right))
    return max(float((left[name] - right[name]).abs().max()) for name in shared)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--json_out",
        default="tmp/t5gemma2_coqview_history_gradient_policy_20260718.json",
    )
    args = parser.parse_args()

    torch.manual_seed(3)
    config = tiny_config()
    base = T5Gemma2ForConditionalGeneration(config).float().eval()
    retained = copy.deepcopy(base)
    detached_sum = copy.deepcopy(base)
    detached_stream = copy.deepcopy(base)
    public_training = wrap_tiny_model(base)
    public_inference = wrap_tiny_model(base)

    retained_logits, retained_losses = run_steps(retained, config, False, False)
    detached_logits, detached_losses = run_steps(detached_sum, config, True, False)
    stream_logits, stream_losses = run_steps(detached_stream, config, True, True)
    public_train_losses = public_training_losses(public_training)
    public_infer_losses = public_inference_losses(public_inference)

    retained_gradients = gradients(retained)
    detached_gradients = gradients(detached_sum)
    stream_gradients = gradients(detached_stream)
    forward_max_diff = max_logit_difference(retained_logits, detached_logits)
    stream_forward_max_diff = max_logit_difference(detached_logits, stream_logits)
    stream_gradient_max_diff = max_gradient_difference(detached_gradients, stream_gradients)
    retained_gradient_differences = {
        name: float((retained_gradients[name] - detached_gradients[name]).abs().max())
        for name in sorted(set(retained_gradients) & set(detached_gradients))
        if not torch.equal(retained_gradients[name], detached_gradients[name])
    }

    invalid_policy_rejected = False
    try:
        next(
            MyT5Gemma2withCoq1.coqview_step_losses(
                object(),
                None,
                None,
                None,
                None,
                history_gradient_policy="unrecorded_policy",
            )
        )
    except ValueError:
        invalid_policy_rejected = True

    assert forward_max_diff == 0.0
    assert stream_forward_max_diff == 0.0
    assert retained_losses == detached_losses == stream_losses
    assert public_train_losses == public_infer_losses
    assert stream_gradient_max_diff < 1e-5
    assert retained_gradient_differences
    assert invalid_policy_rejected

    result = {
        "policy": POLICY,
        "torch_version": torch.__version__,
        "transformers_version": transformers.__version__,
        "target_steps": len(retained_losses),
        "public_training_vs_inference_losses_exact": True,
        "public_training_losses": public_train_losses,
        "public_inference_losses": public_infer_losses,
        "retained_history_loss_sum": sum(retained_losses),
        "detached_history_loss_sum": sum(detached_losses),
        "retained_vs_detached_max_logit_abs_diff": forward_max_diff,
        "detached_sum_vs_stream_max_logit_abs_diff": stream_forward_max_diff,
        "detached_sum_vs_stream_max_gradient_abs_diff": stream_gradient_max_diff,
        "retained_vs_detached_different_gradient_tensor_count": len(
            retained_gradient_differences
        ),
        "retained_vs_detached_max_gradient_abs_diff": max(
            retained_gradient_differences.values()
        ),
        "unknown_policy_rejected": invalid_policy_rejected,
        "conclusion": (
            "Detaching self-attention K/V preserves cached forward logits and scalar "
            "losses exactly. Immediate per-target backward matches summed detached "
            "backward, while retained-history gradients intentionally differ."
        ),
    }
    output = Path(args.json_out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
