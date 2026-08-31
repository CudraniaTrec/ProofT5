from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class HFRuntime:
    torch: Any
    tokenizer: Any
    model: Any
    device: Any
    family: str


def load_hf_runtime(
    *,
    model_path: str,
    tokenizer_path: str,
    device: str,
    dtype: str,
    local_files_only: bool,
    model_family: str = "auto",
) -> HFRuntime:
    """Load either a causal LM or an encoder-decoder checkpoint.

    The frozen ordinary Java checkpoints contain weights/config only, so their
    tokenizer must be loaded from the retained T5Gemma2 base-model directory.
    """
    import torch
    from transformers import (
        AutoConfig,
        AutoModelForCausalLM,
        AutoModelForSeq2SeqLM,
        AutoTokenizer,
    )

    tokenizer = AutoTokenizer.from_pretrained(
        tokenizer_path or model_path,
        local_files_only=local_files_only,
        trust_remote_code=True,
    )
    config = AutoConfig.from_pretrained(
        model_path,
        local_files_only=local_files_only,
        trust_remote_code=True,
    )
    family = model_family
    if family == "auto":
        family = "seq2seq" if bool(getattr(config, "is_encoder_decoder", False)) else "causal"
    if family not in {"causal", "seq2seq"}:
        raise ValueError(f"unsupported Hugging Face model family: {family}")

    torch_dtype = {
        "auto": "auto",
        "bf16": torch.bfloat16,
        "fp16": torch.float16,
        "fp32": torch.float32,
    }[dtype]
    kwargs = {
        "local_files_only": local_files_only,
        "trust_remote_code": True,
        # ``torch_dtype`` works in the upstream-pinned Transformers 4.x
        # environment and remains a supported (deprecated) alias in 5.x.
        "torch_dtype": torch_dtype,
    }
    if device == "auto":
        kwargs["device_map"] = "auto"
    loader = AutoModelForSeq2SeqLM if family == "seq2seq" else AutoModelForCausalLM
    model = loader.from_pretrained(model_path, **kwargs).eval()
    if device != "auto":
        model.to(device)
    return HFRuntime(torch, tokenizer, model, next(model.parameters()).device, family)


def decoder_start_token_id(model, tokenizer) -> int:
    values = (
        getattr(model.generation_config, "decoder_start_token_id", None),
        getattr(model.config, "decoder_start_token_id", None),
        getattr(model.generation_config, "bos_token_id", None),
        getattr(model.config, "bos_token_id", None),
        tokenizer.bos_token_id,
        tokenizer.pad_token_id,
    )
    try:
        return int(next(value for value in values if value is not None))
    except StopIteration as exc:
        raise RuntimeError("encoder-decoder checkpoint has no decoder start token") from exc
