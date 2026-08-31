from __future__ import annotations

import argparse
import json
import pickle
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


def initialize(args: argparse.Namespace) -> dict:
    model_path = Path(args.model)
    tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        local_files_only=True,
        dtype=torch.bfloat16,
    )
    source_embeddings = model.get_input_embeddings().weight.detach().cpu()
    with Path(args.rules).open("rb") as handle:
        rules = pickle.load(handle)
    vocab_size = max(rules.values()) + 1
    if len(rules) != vocab_size:
        raise ValueError("DSL rule ids must be contiguous")
    id_to_text = [None] * vocab_size
    for text, index in rules.items():
        id_to_text[index] = text
    output = torch.empty(
        (vocab_size, source_embeddings.size(1)), dtype=torch.bfloat16
    )
    for start in range(0, vocab_size, args.batch_size):
        texts = [text if text else tokenizer.eos_token for text in id_to_text[start : start + args.batch_size]]
        encoded = tokenizer(
            texts,
            add_special_tokens=False,
            padding=True,
            return_tensors="pt",
        )
        ids = encoded["input_ids"]
        mask = encoded["attention_mask"].unsqueeze(-1)
        pooled = (source_embeddings[ids] * mask).sum(dim=1) / mask.sum(
            dim=1
        ).clamp_min(1)
        output[start : start + len(texts)] = pooled.to(torch.bfloat16)
    output[args.pad_id].zero_()
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    torch.save(output, destination)
    result = {
        "model": str(model_path),
        "rules": args.rules,
        "output": str(destination),
        "vocab_size": vocab_size,
        "hidden_size": int(output.size(1)),
        "dtype": str(output.dtype),
        "initialization": (
            "mean Qwen input embedding of each frozen ProofT5 DSL token string"
        ),
    }
    destination.with_suffix(".json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Initialize the frozen ProofT5 DSL vocabulary from Qwen embeddings."
    )
    parser.add_argument("--model", default="Utils/models/Qwen2.5-Coder-3B")
    parser.add_argument(
        "--rules",
        default="Utils/data/mbjpcoqview_clean673_from_java_clean30_fullseq_20260810/rules.pkl",
    )
    parser.add_argument(
        "--output",
        default="Utils/models/Qwen2.5-Coder-3B/prooft5_dsl_embedding_init.pt",
    )
    parser.add_argument("--batch_size", type=int, default=1024)
    parser.add_argument("--pad_id", type=int, default=0)
    args = parser.parse_args()
    initialize(args)


if __name__ == "__main__":
    main()
