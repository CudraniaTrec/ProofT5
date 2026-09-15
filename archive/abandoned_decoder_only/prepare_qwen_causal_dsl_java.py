from __future__ import annotations

import argparse
import json
import pickle
import shutil
from pathlib import Path

from transformers import AutoTokenizer


REPO_ROOT = Path(__file__).resolve().parent


def load_source_tokenizer(task_dir: Path):
    for name in ("tokenizer.pkl", "coq_tokenizer.pkl"):
        path = task_dir / name
        if path.is_file():
            with path.open("rb") as handle:
                return pickle.load(handle)
    raise FileNotFoundError(f"no source tokenizer under {task_dir}")


def retokenize_rows(rows, source_tokenizer, qwen_tokenizer):
    converted = []
    for row in rows:
        updated = dict(row)
        natural_language = source_tokenizer.decode(
            row["nl"], skip_special_tokens=True
        )
        updated["nl"] = qwen_tokenizer.encode(
            natural_language, add_special_tokens=False
        )
        converted.append(updated)
    return converted


def copy_runtime_assets(source: Path, target: Path) -> None:
    for name in ("rules.pkl", "tokenizer.pkl", "coq_tokenizer.pkl"):
        path = source / name
        if path.is_file():
            shutil.copy2(path, target / name)


def write_task(
    *,
    source: Path,
    target: Path,
    qwen_tokenizer,
    base_model_name: str,
    dsl_embedding_init: str,
    enable_coqview: bool,
    evaluation: bool,
) -> dict:
    target.mkdir(parents=True, exist_ok=False)
    source_tokenizer = load_source_tokenizer(source)
    split_counts = {}
    max_nl_len = 0
    for split in ("train", "valid", "test"):
        path = source / f"{split}.pkl"
        rows = pickle.load(path.open("rb")) if path.is_file() else []
        converted = retokenize_rows(rows, source_tokenizer, qwen_tokenizer)
        with (target / f"{split}.pkl").open("wb") as handle:
            pickle.dump(converted, handle, protocol=pickle.HIGHEST_PROTOCOL)
        split_counts[split] = len(converted)
        max_nl_len = max(
            max_nl_len,
            max((len(row["nl"]) for row in converted), default=0),
        )
    copy_runtime_assets(source, target)
    source_config = json.loads((source / "config.json").read_text())
    config = dict(source_config)
    continue_from_ordinary = bool(enable_coqview and not evaluation)
    ordinary_model_task = target.name.replace("pretrain_", "", 1).replace(
        "_coqview_", "_plain_"
    )
    config.update(
        {
            "model_family": "qwen_causal_dsl",
            "base_model_name": base_model_name,
            "model_parameter_dtype": "bf16",
            "precision": "bf16",
            "local_files_only": True,
            "init_from_hf": not continue_from_ordinary,
            "strict_model_loading": True,
            "enable_coqview": enable_coqview,
            "cut_prefix": True,
            "validation": False,
            "evaluation_only": evaluation,
            "batch_size": 1,
            "batch_size_eval": 1,
            "lr": 1e-6 if continue_from_ordinary else 2e-5,
            "coq_feature_lr": 1e-5 if continue_from_ordinary else None,
            "coq_feature_only": bool(continue_from_ordinary),
            "coq_adapter_initialization": (
                "zero_projection_unit_gate" if continue_from_ordinary else None
            ),
            "max_epoch": 20,
            "save_last_only": False,
            "NlLen": max_nl_len,
            "nl_pad_token_id": int(qwen_tokenizer.pad_token_id),
            "pad_token_id": 0,
            "mask_id": 0,
            "dsl_embedding_init": dsl_embedding_init,
            "force_coq_decoder": True,
            "qwen_tokenizer": base_model_name,
            "pretrain_name": (
                ordinary_model_task
                if continue_from_ordinary
                else source_config.get("pretrain_name", "")
            ),
            "pretrain_model_type": (
                "selected"
                if continue_from_ordinary
                else source_config.get("pretrain_model_type", "last")
            ),
            "data_revision": "qwen-causal-dsl-retokenized-clean673-v1",
            "checkpoint_selection": (
                "minimum global training-token loss among prespecified epochs; "
                "no validation or test metrics"
            ),
            "source_task": source.name,
            "split_counts": split_counts,
        }
    )
    (target / "config.json").write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n"
    )
    return {
        "target": str(target),
        "source": str(source),
        "enable_coqview": enable_coqview,
        "evaluation_only": evaluation,
        "split_counts": split_counts,
        "max_nl_len": max_nl_len,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Retokenize frozen ProofT5 DSL tasks for a Qwen causal backbone."
    )
    parser.add_argument(
        "--train_source",
        default="Utils/data/mbjpcoqview_clean673_from_java_clean30_fullseq_20260810",
    )
    parser.add_argument(
        "--test_source",
        default="Utils/data/mbjp_original_test_coqview_cleanjava_20260810",
    )
    parser.add_argument(
        "--model", default="Utils/models/Qwen2.5-Coder-3B"
    )
    parser.add_argument(
        "--dsl_embedding_init",
        default="Utils/models/Qwen2.5-Coder-3B/prooft5_dsl_embedding_init.pt",
    )
    parser.add_argument("--suffix", default="20260825")
    args = parser.parse_args()

    model_path = Path(args.model)
    tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    task_root = REPO_ROOT / "Utils" / "data"
    specifications = [
        (
            Path(args.train_source),
            task_root / f"pretrain_qwen25coder3b_java_clean673_plain_{args.suffix}",
            False,
            False,
        ),
        (
            Path(args.train_source),
            task_root / f"pretrain_qwen25coder3b_java_clean673_coqview_{args.suffix}",
            True,
            False,
        ),
        (
            Path(args.test_source),
            task_root / f"qwen25coder3b_mbjp_plain_eval_{args.suffix}",
            False,
            True,
        ),
        (
            Path(args.test_source),
            task_root / f"qwen25coder3b_mbjp_coqview_eval_{args.suffix}",
            True,
            True,
        ),
    ]
    manifest = [
        write_task(
            source=source,
            target=target,
            qwen_tokenizer=tokenizer,
            base_model_name=str(model_path),
            dsl_embedding_init=args.dsl_embedding_init,
            enable_coqview=coqview,
            evaluation=evaluation,
        )
        for source, target, coqview, evaluation in specifications
    ]
    output = task_root / f"qwen25coder3b_causal_dsl_manifest_{args.suffix}.json"
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(output)


if __name__ == "__main__":
    main()
