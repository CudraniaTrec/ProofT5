from __future__ import annotations

"""Prepare CodeGemma tasks while changing only the output representation.

The natural-language side is retokenized with CodeGemma's tokenizer.  The
target side is kept as the frozen ProofT5 rule vocabulary, so the resulting
model is still evaluated by the audited grammar decoder and can be compared
with the existing ProofT5 rows.  The MBJP evaluation prompt is sanitized by
removing Javadoc input/output examples; the hidden Java harness is copied
unchanged and is never passed to the model.
"""

import argparse
import copy
import json
import pickle
import re
from pathlib import Path

from transformers import AutoTokenizer


ROOT = Path(__file__).resolve().parent
IO_EXAMPLE_RE = re.compile(r"^\s*\*\s*(?:>|(?:input|output)\s*:)", re.I)


def load_pickle(path: Path):
    with path.open("rb") as handle:
        return pickle.load(handle)


def dump_pickle(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        pickle.dump(value, handle, protocol=pickle.HIGHEST_PROTOCOL)


def source_tokenizer(task: Path):
    for name in ("coq_tokenizer.pkl", "tokenizer.pkl"):
        path = task / name
        if path.is_file():
            return load_pickle(path)
    raise FileNotFoundError(f"no source tokenizer under {task}")


def strip_io_examples(text: str) -> str:
    # Keep the Javadoc and task wording, deleting each concrete input example
    # and its immediately following expected-output line, matching the frozen
    # decoder-only no-I/O preparation utility.
    output = []
    in_doc = False
    skip_output = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("/**"):
            in_doc = True
        if in_doc and IO_EXAMPLE_RE.match(line):
            skip_output = True
            continue
        if skip_output:
            skip_output = False
            if stripped.startswith("*") and stripped != "*/":
                continue
        if in_doc and stripped == "*/":
            in_doc = False
        output.append(line)
    return "\n".join(output)


def convert_rows(
    rows,
    old_tokenizer,
    new_tokenizer,
    sanitize_nl=False,
    add_special_tokens=False,
):
    converted = []
    for row in rows:
        updated = copy.deepcopy(row)
        natural_language = old_tokenizer.decode(
            row["nl"], skip_special_tokens=True
        )
        if sanitize_nl:
            natural_language = strip_io_examples(natural_language)
        updated["nl"] = new_tokenizer.encode(
            natural_language, add_special_tokens=add_special_tokens
        )
        converted.append(updated)
    return converted


def write_task(
    *,
    source: Path,
    target: Path,
    tokenizer,
    base_model: str,
    model_family: str,
    init_from_hf: bool,
    pretrain_name: str,
    evaluation_only: bool,
    sanitize_nl: bool = False,
    max_epoch: int,
    cut_prefix: bool,
    dsl_embedding_init: str,
    add_special_tokens: bool = False,
) -> dict:
    if target.exists():
        raise FileExistsError(f"refusing to overwrite existing task: {target}")
    target.mkdir(parents=True)
    old_tokenizer = source_tokenizer(source)
    split_counts = {}
    max_nl_len = 0
    max_code_len = 0
    for split in ("train", "valid", "test"):
        source_path = source / f"{split}.pkl"
        rows = load_pickle(source_path) if source_path.is_file() else []
        converted = convert_rows(
            rows,
            old_tokenizer,
            tokenizer,
            sanitize_nl=sanitize_nl,
            add_special_tokens=add_special_tokens,
        )
        dump_pickle(target / f"{split}.pkl", converted)
        split_counts[split] = len(converted)
        max_nl_len = max(
            max_nl_len, max((len(row.get("nl", [])) for row in converted), default=0)
        )
        max_code_len = max(
            max_code_len,
            max((len(row.get("rulelist", [])) for row in converted), default=0),
        )

    # Decoder-side stringification must continue to use the frozen DSL
    # tokenizer/rules, not CodeGemma's natural-language tokenizer.
    for name in ("rules.pkl", "rules.json", "tokenizer.pkl", "coq_tokenizer.pkl"):
        source_path = source / name
        if source_path.is_file():
            target_path = target / name
            target_path.write_bytes(source_path.read_bytes())

    source_config = json.loads((source / "config.json").read_text())
    config = dict(source_config)
    config.update(
        {
            "model_family": model_family,
            "base_model_name": base_model,
            "dsl_embedding_init": dsl_embedding_init,
            "local_files_only": True,
            "init_from_hf": bool(init_from_hf),
            "strict_model_loading": True,
            "pretrain_name": pretrain_name,
            "pretrain_model_type": "last",
            "evaluation_only": bool(evaluation_only),
            "validation": False,
            "batch_size": 1,
            "batch_size_eval": 1,
            "lr": 1e-5,
            "max_epoch": int(max_epoch),
            "eval_step": 5,
            "eval_step_init": 5,
            "cut_prefix": bool(cut_prefix),
            "precision": "bf16",
            "model_parameter_dtype": "bf16",
            "pad_token_id": 0,
            "mask_id": 0,
            "nl_pad_token_id": int(tokenizer.pad_token_id),
            "rulenum": int(source_config.get("rulenum", len(load_pickle(source / "rules.pkl")))),
            "force_coq_decoder": True,
            "disable_coq_check": True,
            "coq_final_only_check": False,
            "beam_size": 10,
            "length_penalty": 0.1,
            "save_last_only": False,
            "pad_train_shards_to_equal_batches": True,
            "train_num_workers": 0,
            "eval_num_workers": 0,
            "data_revision": "codegemma-causal-dsl-frozen-rules-v1",
            "representation": "ProofT5 Coq/DSL rule sequence",
            "decoding_constraint": "grammar only; standalone javac/Coq checks disabled",
            "source_task": str(source),
            "split_counts": split_counts,
            "sanitize_io_examples": bool(sanitize_nl),
            "add_special_tokens": bool(add_special_tokens),
            "max_nl_len": max_nl_len,
            "max_code_len": max_code_len,
            # Avoid silently truncating the longest rule sequence from the
            # source task (the historical pretraining config used a lower
            # nominal CodeLen than its observed maximum).
            "CodeLen": max_code_len,
            "NlLen": max_nl_len,
        }
    )
    (target / "config.json").write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n"
    )
    return {
        "source": str(source),
        "target": str(target),
        "split_counts": split_counts,
        "max_nl_len": max_nl_len,
        "max_code_len": max_code_len,
        "sanitize_io_examples": bool(sanitize_nl),
        "add_special_tokens": bool(add_special_tokens),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="Utils/models/CodeGemma-2B")
    parser.add_argument(
        "--pretrain-source", default="Utils/data/pretrain_t5gemma2_2b_retok"
    )
    parser.add_argument(
        "--java-source", default="Utils/data/mbjp_humaneval_half_train_t5gemma2_20260731"
    )
    parser.add_argument(
        "--test-source", default="Utils/data/mbjp_original_test_t5gemma2_20260731"
    )
    parser.add_argument("--suffix", default="20260826")
    parser.add_argument(
        "--add-special-tokens",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Include the CodeGemma BOS token on each natural-language prompt.",
    )
    args = parser.parse_args()

    model_path = Path(args.model)
    tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token

    data_root = ROOT / "Utils" / "data"
    pretrain_name = f"pretrain_codegemma2b_java_rules_{args.suffix}"
    java_name = f"codegemma2b_java_rules_673_{args.suffix}"
    eval_name = f"codegemma2b_mbjp_eval_noio_{args.suffix}"
    init_path = model_path / "prooft5_dsl_embedding_init.pt"

    manifest = []
    manifest.append(
        write_task(
            source=Path(args.pretrain_source),
            target=data_root / pretrain_name,
            tokenizer=tokenizer,
            base_model=str(model_path),
            model_family="codegemma_causal_dsl",
            init_from_hf=True,
            pretrain_name="grammart5-base",
            evaluation_only=False,
            max_epoch=4,  # five complete passes, matching corrected ProofT5 pretrain
            cut_prefix=False,
            dsl_embedding_init=str(init_path),
            add_special_tokens=args.add_special_tokens,
        )
    )
    manifest.append(
        write_task(
            source=Path(args.java_source),
            target=data_root / java_name,
            tokenizer=tokenizer,
            base_model=str(model_path),
            model_family="codegemma_causal_dsl",
            init_from_hf=False,
            pretrain_name=pretrain_name,
            evaluation_only=False,
            max_epoch=29,  # thirty complete Java passes
            cut_prefix=True,
            dsl_embedding_init=str(init_path),
            add_special_tokens=args.add_special_tokens,
        )
    )
    manifest.append(
        write_task(
            source=Path(args.test_source),
            target=data_root / eval_name,
            tokenizer=tokenizer,
            base_model=str(model_path),
            model_family="codegemma_causal_dsl",
            init_from_hf=True,
            pretrain_name=java_name,
            evaluation_only=True,
            sanitize_nl=True,
            max_epoch=0,
            cut_prefix=False,
            dsl_embedding_init=str(init_path),
            add_special_tokens=args.add_special_tokens,
        )
    )
    output = data_root / f"codegemma2b_causal_dsl_manifest_{args.suffix}.json"
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(output)
    print(f"DSL embedding initialization: {init_path}")


if __name__ == "__main__":
    main()
