#!/usr/bin/env python3
"""Fail if a complete CoqView task would be silently truncated in training."""

import argparse
import json
import pickle
from pathlib import Path


def load_rows(path):
    with path.open("rb") as handle:
        return pickle.load(handle)


def decoder_position_limit(model_config):
    decoder = model_config.get("decoder", {})
    limit = decoder.get("max_position_embeddings")
    if limit is None:
        raise ValueError("model config has no decoder.max_position_embeddings")
    return int(limit)


def encoder_position_limit(model_config):
    encoder = model_config.get("encoder", {})
    text_config = encoder.get("text_config", {})
    limit = text_config.get("max_position_embeddings")
    if limit is None:
        raise ValueError(
            "model config has no encoder.text_config.max_position_embeddings"
        )
    return int(limit)


def audit_split(rows, config, split, encoder_limit, decoder_limit):
    nl_cap = int(config["NlLen"])
    # run.py deliberately replaces CodeLen with max_code_len after loading a
    # task config. With cut_prefix=True this is the suffix cap, not the full
    # prefix+target length.
    suffix_cap = int(config["max_code_len"])
    context_cap = int(config["max_coqview_len"])
    cut_prefix = bool(config.get("cut_prefix"))
    if not cut_prefix:
        raise ValueError("complete CoqView bounds audit requires cut_prefix=true")

    maxima = {
        "nl_tokens": 0,
        "full_target_tokens": 0,
        "prefix_tokens": 0,
        "suffix_tokens": 0,
        "coqview_tokens": 0,
        "decoder_positions": 0,
        "encoder_tokens_actual": 0,
    }
    violations = []
    active_targets = 0
    for index, row in enumerate(rows):
        target = row["rulelist"][1:-1]
        prefix = row["prefix"]
        if target[: len(prefix)] != prefix:
            violations.append(f"{split}[{index}] prefix does not match target")
            continue
        suffix = target[len(prefix) :]
        contexts = row["coqview"][max(len(prefix) - 1, 0) :]
        if len(contexts) != len(suffix):
            violations.append(
                f"{split}[{index}] has {len(contexts)} cut contexts for "
                f"{len(suffix)} suffix targets"
            )
        row_context_max = max((len(context) for context in contexts), default=0)
        decoder_positions = max(0, len(prefix) + len(suffix) - 1)
        encoder_tokens_actual = len(row["nl"]) + row_context_max
        active_targets += len(suffix)

        observed = {
            "nl_tokens": len(row["nl"]),
            "full_target_tokens": len(target),
            "prefix_tokens": len(prefix),
            "suffix_tokens": len(suffix),
            "coqview_tokens": row_context_max,
            "decoder_positions": decoder_positions,
            "encoder_tokens_actual": encoder_tokens_actual,
        }
        for key, value in observed.items():
            maxima[key] = max(maxima[key], value)
        if observed["nl_tokens"] > nl_cap:
            violations.append(
                f"{split}[{index}] NL {observed['nl_tokens']} > NlLen {nl_cap}"
            )
        if observed["suffix_tokens"] > suffix_cap:
            violations.append(
                f"{split}[{index}] suffix {observed['suffix_tokens']} > "
                f"max_code_len {suffix_cap}"
            )
        if observed["coqview_tokens"] > context_cap:
            violations.append(
                f"{split}[{index}] context {observed['coqview_tokens']} > "
                f"max_coqview_len {context_cap}"
            )
        if decoder_positions > decoder_limit:
            violations.append(
                f"{split}[{index}] decoder positions {decoder_positions} > "
                f"model limit {decoder_limit}"
            )
        if encoder_tokens_actual > encoder_limit:
            violations.append(
                f"{split}[{index}] encoder tokens {encoder_tokens_actual} > "
                f"model limit {encoder_limit}"
            )

    # The collator pads NL and context independently before concatenation.
    encoder_padded_bound = nl_cap + context_cap
    if encoder_padded_bound > encoder_limit:
        violations.append(
            f"configured padded encoder bound {encoder_padded_bound} > "
            f"model limit {encoder_limit}"
        )
    if violations:
        raise ValueError("; ".join(violations[:20]))
    return {
        "rows": len(rows),
        "active_suffix_targets": active_targets,
        "caps": {
            "NlLen": nl_cap,
            "effective_training_CodeLen": suffix_cap,
            "max_coqview_len": context_cap,
            "encoder_position_limit": encoder_limit,
            "decoder_position_limit": decoder_limit,
            "encoder_padded_bound": encoder_padded_bound,
        },
        "maxima": maxima,
        "unexpected_truncation_risk": False,
    }


def audit_task(task_dir, model_config_path):
    config = json.loads((task_dir / "config.json").read_text())
    model_config = json.loads(model_config_path.read_text())
    encoder_limit = encoder_position_limit(model_config)
    decoder_limit = decoder_position_limit(model_config)
    return {
        "status": "ok",
        "task_dir": str(task_dir),
        "model_config": str(model_config_path),
        "splits": {
            split: audit_split(
                load_rows(task_dir / f"{split}.pkl"),
                config,
                split,
                encoder_limit,
                decoder_limit,
            )
            for split in ("train", "test")
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("task_dir", type=Path)
    parser.add_argument(
        "--model_config",
        type=Path,
        default=Path("Utils/models/t5gemma-2-1b-1b/config.json"),
    )
    parser.add_argument("--json_out", type=Path)
    args = parser.parse_args()
    report = audit_task(args.task_dir, args.model_config)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.json_out:
        args.json_out.write_text(rendered)
    print(rendered, end="")


if __name__ == "__main__":
    main()
