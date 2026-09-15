from __future__ import annotations

import argparse
import json
from pathlib import Path

from transformers import AutoTokenizer

from prepare_qwen_causal_dsl_java import REPO_ROOT, write_task


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare the clean Java Coq-representation pair for a general "
            "Qwen causal backbone. This is Coq-only, never CoqView."
        )
    )
    parser.add_argument("--model", default="Utils/models/Qwen2.5-3B")
    parser.add_argument(
        "--dsl_embedding_init",
        default="Utils/models/Qwen2.5-3B/prooft5_dsl_embedding_init.pt",
    )
    parser.add_argument(
        "--train_source",
        default="Utils/data/mbjp_humaneval_half_train_t5gemma2_20260731",
    )
    parser.add_argument(
        "--test_source",
        default="Utils/data/mbjp_original_test_t5gemma2_20260731",
    )
    parser.add_argument("--suffix", default="20260826")
    args = parser.parse_args()

    model_path = Path(args.model)
    tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    task_root = REPO_ROOT / "Utils" / "data"
    train_target = task_root / f"pretrain_qwen25_3b_java_clean673_coq_{args.suffix}"
    test_target = task_root / f"qwen25_3b_mbjp_coq_eval_{args.suffix}"
    manifest = []
    for source, target, evaluation in (
        (Path(args.train_source), train_target, False),
        (Path(args.test_source), test_target, True),
    ):
        entry = write_task(
            source=source,
            target=target,
            qwen_tokenizer=tokenizer,
            base_model_name=str(model_path),
            dsl_embedding_init=args.dsl_embedding_init,
            enable_coqview=False,
            evaluation=evaluation,
        )
        config_path = target / "config.json"
        config = json.loads(config_path.read_text())
        config.update(
            {
                "enable_coqview": False,
                "experiment_variant": "coq_representation_syntax_pruning",
                "force_coq_decoder": True,
                "disable_coq_check": True,
                "max_epoch": 19,
                "eval_step": 5,
                "eval_step_init": 5,
                "save_last_only": False,
                "pad_train_shards_to_equal_batches": True,
                "checkpoint_epochs": [5, 10, 15, 20],
                "representation": "ProofT5 Coq/DSL rule sequence",
                "decoding_constraint": "grammar only; coqc disabled",
                "data_revision": "qwen25-general-coq-clean673-v1",
            }
        )
        config_path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n")
        manifest.append(entry)
    output = task_root / f"qwen25_3b_coq_manifest_{args.suffix}.json"
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(output)


if __name__ == "__main__":
    main()
