#!/usr/bin/env python3
import argparse
import copy
import json
import pickle
import shutil
from pathlib import Path

from tqdm import tqdm

from SuFu.sufu_model import detokenize


DEFAULT_SOURCE = "sufucoq_t5gemma2_2b_retok_promptprefix_lr1e4_from_java"
DEFAULT_TARGET = (
    "sufucoqview_t5gemma2_2b_retok_promptprefix_ctxfix_"
    "lr5e5_from_sufu_anchor16"
)


def load_pickle(path):
    with path.open("rb") as handle:
        return pickle.load(handle)


def dump_pickle(value, path):
    with path.open("wb") as handle:
        pickle.dump(value, handle)


def build_contexts(row, tokenizer, rules, split, row_index):
    target_ids = row["rulelist"][1:-1]
    prefix = row["prefix"]
    if target_ids[: len(prefix)] != prefix:
        raise ValueError(f"{split}[{row_index}] prefix does not match target")

    tokens = tokenizer.convert_ids_to_tokens(target_ids)
    _, type_contexts = detokenize(tokens)
    if len(type_contexts) != len(target_ids) - 1:
        raise ValueError(
            f"{split}[{row_index}] context count {len(type_contexts)} "
            f"!= target length - 1 ({len(target_ids) - 1})"
        )

    encoded = []
    for step, context_tokens in enumerate(type_contexts):
        missing = [token for token in context_tokens if token not in rules]
        if missing:
            raise KeyError(
                f"{split}[{row_index}] step {step} has missing context tokens: "
                f"{missing[:10]}"
            )
        encoded.append(tokenizer.convert_tokens_to_ids(context_tokens))
    return encoded


def convert_split(source_dir, target_dir, split, tokenizer, rules):
    rows = load_pickle(source_dir / f"{split}.pkl")
    converted = []
    max_context_len = 0
    total_contexts = 0
    for row_index, row in enumerate(tqdm(rows, desc=f"ctxfix:{split}")):
        new_row = copy.deepcopy(row)
        contexts = build_contexts(row, tokenizer, rules, split, row_index)
        new_row["coqview"] = contexts
        converted.append(new_row)
        total_contexts += len(contexts)
        if contexts:
            max_context_len = max(max_context_len, max(map(len, contexts)))

    dump_pickle(converted, target_dir / f"{split}.pkl")
    (target_dir / f"{split}.json").write_text(
        json.dumps(converted, indent=2) + "\n"
    )
    return {
        "rows": len(converted),
        "contexts": total_contexts,
        "max_context_len": max_context_len,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-task", default=DEFAULT_SOURCE)
    parser.add_argument("--target-task", default=DEFAULT_TARGET)
    parser.add_argument("--data-root", default="Utils/data")
    parser.add_argument("--model-root", default="Utils/models")
    args = parser.parse_args()

    data_root = Path(args.data_root)
    source_dir = data_root / args.source_task
    target_dir = data_root / args.target_task
    if target_dir.exists():
        raise FileExistsError(f"Refusing to overwrite existing task: {target_dir}")
    target_dir.mkdir(parents=True)

    tokenizer = load_pickle(source_dir / "tokenizer.pkl")
    rules = load_pickle(source_dir / "rules.pkl")
    report = {
        "source_task": args.source_task,
        "target_task": args.target_task,
        "context_encoding": "convert_tokens_to_ids(extract_ctx())",
        "vocab_size": len(rules),
        "splits": {},
    }

    try:
        for split in ("train", "test"):
            report["splits"][split] = convert_split(
                source_dir, target_dir, split, tokenizer, rules
            )

        for artifact in (
            "tokenizer.pkl",
            "coq_tokenizer.pkl",
            "rules.pkl",
            "rules.json",
        ):
            shutil.copy2(source_dir / artifact, target_dir / artifact)

        config = json.loads((source_dir / "config.json").read_text())
        config.update({
            "lr": 5e-5,
            "max_epoch": 5,
            "eval_step": 5,
            "eval_step_init": 5,
            "validation": False,
            "cut_prefix": True,
            "enable_coqview": True,
            "coqview_train_steps": 16,
            "coqview_anchor_first_steps": 16,
            "coqview_random_window_steps": 0,
            "coqview_max_step_offset": 0,
            "coqview_prefix_replay_steps": 0,
            "coqview_prefix_replay_repeats": 0,
            "pretrain_name": args.source_task,
            "max_coqview_len": max(
                split["max_context_len"] for split in report["splits"].values()
            ),
            "data_revision": "sufu-coqview-ctxfix-v1",
            "context_encoding": report["context_encoding"],
        })
        (target_dir / "config.json").write_text(json.dumps(config, indent=2) + "\n")

        lineage = {
            "model_base": args.source_task,
            "data_source": args.source_task,
            "stage": "sufu_coqview_anchor16",
            "data_revision": config["data_revision"],
        }
        (target_dir / "lineage.json").write_text(json.dumps(lineage, indent=2) + "\n")
        (target_dir / "build_report.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )
        (Path(args.model_root) / f"Model{args.target_task}").mkdir(parents=True, exist_ok=True)
    except Exception:
        shutil.rmtree(target_dir)
        raise

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
