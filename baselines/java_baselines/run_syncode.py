from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from baselines.java_baselines.common import (
    CandidateWriter,
    align_tasks_to_score,
    common_manifest,
    load_java_tasks,
    output_directory,
    select_tasks,
)
from baselines.java_baselines.syncode_cache_guard import (
    finalize_mask_store,
    prepare_mask_store,
)


def load_runtime(args):
    try:
        import torch
        from syncode import Grammar, SyncodeLogitsProcessor
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as exc:
        raise RuntimeError(
            "SynCode runtime is missing. Run baselines/java_baselines/bootstrap_envs.sh "
            "and use /data2/x/hzc/.uv-envs/prooft5-syncode-py312/bin/python."
        ) from exc

    tokenizer = AutoTokenizer.from_pretrained(
        args.model,
        local_files_only=args.local_files_only,
        trust_remote_code=True,
    )
    torch_dtype = {
        "auto": "auto",
        "bf16": torch.bfloat16,
        "fp16": torch.float16,
        "fp32": torch.float32,
    }[args.dtype]
    model_kwargs = {
        "local_files_only": args.local_files_only,
        "trust_remote_code": True,
        "torch_dtype": torch_dtype,
    }
    if args.device == "auto":
        model_kwargs["device_map"] = "auto"
    model = AutoModelForCausalLM.from_pretrained(args.model, **model_kwargs).eval()
    if args.device != "auto":
        model.to(args.device)
    device = next(model.parameters()).device
    grammar = Grammar(args.grammar)
    cache_path, metadata_path, cache_metadata = prepare_mask_store(
        tokenizer, grammar, args.syncode_mode, args.rebuild_mask_store
    )
    processor = SyncodeLogitsProcessor(
        grammar=grammar,
        tokenizer=tokenizer,
        use_cache=not args.rebuild_mask_store,
        parse_output_only=False,
        num_samples=1,
        dev_mode=args.dev_mode,
        parser=args.parser,
        mode=args.syncode_mode,
    )
    finalize_mask_store(cache_path, metadata_path, cache_metadata)
    return torch, tokenizer, model, device, processor


def tokenize_prompt(tokenizer, task, device):
    encoded = tokenizer(task.prompt, return_tensors="pt")
    return {key: value.to(device) for key, value in encoded.items()}


def materialize_syncode_candidate(task, suffix: str) -> str:
    return task.prompt + suffix


def run(args: argparse.Namespace) -> Path:
    dataset_path = Path(args.dataset_json)
    loaded_tasks = load_java_tasks(dataset_path, args.dataset_split)
    all_tasks, score_dataset_path = align_tasks_to_score(
        loaded_tasks, args.score_task, args.score_split
    )
    tasks = select_tasks(all_tasks, args.indices, args.limit)
    target = output_directory(args.score_task, args.score_split, args.output_tag)
    if args.dry_run:
        print(
            {
                "method": "syncode_java_cfg",
                "dataset_rows": len(all_tasks),
                "selected_rows": len(tasks),
                "grammar": args.grammar,
                "score_dataset": str(score_dataset_path),
            }
        )
        return target

    torch, tokenizer, model, device, processor = load_runtime(args)
    writer = CandidateWriter(target, resume=args.resume)
    for task in tasks:
        inputs = tokenize_prompt(tokenizer, task, device)
        prompt_length = int(inputs["input_ids"].shape[-1])
        for rank in range(args.candidates):
            if args.resume and not writer.pending(task.index, rank):
                continue
            seed = args.seed + task.index * args.candidates + rank
            torch.manual_seed(seed)
            processor.reset()
            started = time.perf_counter()
            generation_kwargs = {
                "max_new_tokens": args.max_new_tokens,
                "do_sample": args.temperature > 0,
                "pad_token_id": (
                    tokenizer.pad_token_id
                    if tokenizer.pad_token_id is not None
                    else tokenizer.eos_token_id
                ),
                "eos_token_id": tokenizer.eos_token_id,
                "logits_processor": [processor],
            }
            if args.temperature > 0:
                generation_kwargs.update(
                    temperature=args.temperature,
                    top_p=args.top_p,
                    top_k=args.top_k,
                )
            generated = model.generate(**inputs, **generation_kwargs)
            completion_ids = generated[0, prompt_length:]
            raw = tokenizer.decode(completion_ids, skip_special_tokens=True)
            source = materialize_syncode_candidate(task, raw)
            writer.write(
                task.index,
                rank,
                source,
                {
                    "method": "syncode_java_cfg",
                    "task_id": task.task_id,
                    "problem_index": task.index,
                    "candidate_rank": rank,
                    "seed": seed,
                    "model": args.model,
                    "grammar": args.grammar,
                    "syncode_mode": args.syncode_mode,
                    "lm_prompt_mode": "raw_prefix",
                    "raw_response": raw,
                    "source": source,
                    "input_tokens": prompt_length,
                    "output_tokens": int(completion_ids.shape[-1]),
                    "elapsed_seconds": time.perf_counter() - started,
                },
            )
    writer.write_manifest(
        common_manifest(
            method="syncode_java_cfg",
            dataset_path=dataset_path,
            score_dataset_path=score_dataset_path,
            args=vars(args),
        )
        | {
            "model": args.model,
            "constraint_scope": "Java context-free syntax only; no type guarantee",
        }
    )
    print(f"saved candidates to {target}")
    return target


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SynCode Java baseline adapter.")
    parser.add_argument("--dataset_json", required=True)
    parser.add_argument("--dataset_split", default="test")
    parser.add_argument("--score_task", required=True)
    parser.add_argument("--score_split", choices=["train", "valid", "test"], default="test")
    parser.add_argument("--output_tag", required=True)
    parser.add_argument("--model", default="")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--dtype", choices=["auto", "bf16", "fp16", "fp32"], default="bf16")
    parser.add_argument("--local_files_only", action="store_true")
    parser.add_argument("--grammar", default="java")
    parser.add_argument("--syncode_mode", choices=["grammar_mask", "grammar_strict"], default="grammar_mask")
    parser.add_argument("--parser", choices=["lr", "lalr"], default="lalr")
    parser.add_argument("--rebuild_mask_store", action="store_true")
    parser.add_argument("--dev_mode", action="store_true")
    parser.add_argument("--candidates", type=int, default=10)
    parser.add_argument("--max_new_tokens", type=int, default=1024)
    parser.add_argument("--temperature", type=float, default=0.8)
    parser.add_argument("--top_p", type=float, default=0.95)
    parser.add_argument("--top_k", type=int, default=50)
    parser.add_argument("--seed", type=int, default=273567)
    parser.add_argument("--indices", default="")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry_run", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if not args.dry_run and not args.model:
        raise SystemExit("--model is required")
    run(args)


if __name__ == "__main__":
    main()
