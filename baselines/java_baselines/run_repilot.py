from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from baselines.java_baselines.common import (
    CandidateWriter,
    REPO_ROOT,
    align_tasks_to_score,
    common_manifest,
    load_java_tasks,
    output_directory,
    select_tasks,
)
from baselines.java_baselines.jdt_completion import (
    RepilotJdtClient,
    discover_jdt_command,
    trivially_feasible,
)


def load_model(args):
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as exc:
        raise RuntimeError("torch and transformers are required") from exc
    tokenizer = AutoTokenizer.from_pretrained(
        args.model, local_files_only=args.local_files_only, trust_remote_code=True
    )
    dtype = {
        "auto": "auto",
        "bf16": torch.bfloat16,
        "fp16": torch.float16,
        "fp32": torch.float32,
    }[args.dtype]
    kwargs = {
        "local_files_only": args.local_files_only,
        "trust_remote_code": True,
        "torch_dtype": dtype,
    }
    if args.device == "auto":
        kwargs["device_map"] = "auto"
    model = AutoModelForCausalLM.from_pretrained(args.model, **kwargs).eval()
    if args.device != "auto":
        model.to(args.device)
    return torch, tokenizer, model, next(model.parameters()).device


def model_prefix(tokenizer, task, mode: str):
    if mode == "raw_prefix":
        return task.prompt
    messages = [
        {
            "role": "user",
            "content": (
                "Continue the Java source below from the exact final character. "
                "Return only the missing suffix, with no Markdown.\n\n" + task.prompt
            ),
        }
    ]
    return tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )


def generate_one(args, task, rank, torch, tokenizer, model, device, jdt):
    seed = args.seed + task.index * args.candidates + rank
    torch.manual_seed(seed)
    lm_text = model_prefix(tokenizer, task, args.lm_prompt_mode)
    inputs = tokenizer(lm_text, return_tensors="pt").input_ids.to(device)
    model_kwargs = {"use_cache": True}
    past = None
    next_input = inputs
    generated_ids = []
    generated_tokens = []
    rejected = []
    completion_queries = 0
    jdt.open_document(task.prompt)
    started = time.perf_counter()
    for step in range(args.max_new_tokens):
        with torch.no_grad():
            outputs = model(
                input_ids=next_input,
                past_key_values=past,
                use_cache=True,
                return_dict=True,
            )
        past = outputs.past_key_values
        logits = outputs.logits[:, -1, :].float()
        if args.temperature > 0:
            logits = logits / args.temperature
        top_scores, top_ids = torch.topk(logits[0], k=min(args.top_k, logits.shape[-1]))
        weights = torch.softmax(top_scores, dim=-1)
        accepted_id = None
        accepted_token = ""
        while weights.sum().item() > 0:
            if args.temperature > 0:
                local_index = int(torch.multinomial(weights, 1).item())
            else:
                local_index = int(torch.argmax(weights).item())
            token_id = int(top_ids[local_index].item())
            token = tokenizer.decode(
                [token_id], skip_special_tokens=False, clean_up_tokenization_spaces=False
            )
            if token_id == tokenizer.eos_token_id:
                accepted_id, accepted_token = token_id, ""
                break
            source_prefix = task.prompt + "".join(generated_tokens)
            if trivially_feasible(token):
                jdt.update_document(source_prefix + token)
                feasible, continuations = True, None
            else:
                completion_queries += 1
                feasible, continuations = jdt.token_feasible(source_prefix, token)
            if feasible:
                accepted_id, accepted_token = token_id, token
                break
            rejected.append({"step": step, "token_id": token_id, "token": token})
            weights[local_index] = 0
        if accepted_id is None:
            break
        if accepted_id == tokenizer.eos_token_id:
            break
        generated_ids.append(accepted_id)
        generated_tokens.append(accepted_token)
        next_input = torch.tensor([[accepted_id]], device=device)
    suffix = "".join(generated_tokens)
    return task.prompt + suffix, {
        "method": "repilot_jdt_token_pruning",
        "task_id": task.task_id,
        "problem_index": task.index,
        "candidate_rank": rank,
        "seed": seed,
        "model": args.model,
        "lm_prompt_mode": args.lm_prompt_mode,
        "generated_suffix": suffix,
        "generated_token_ids": generated_ids,
        "generated_tokens": generated_tokens,
        "rejected_tokens": rejected,
        "completion_queries": completion_queries,
        "input_tokens": int(inputs.shape[-1]),
        "output_tokens": len(generated_ids),
        "elapsed_seconds": time.perf_counter() - started,
        "upstream_relation": "adapts Repilot's modified-JDT newCompletion pruning policy",
    }


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
                "method": "repilot_jdt_token_pruning",
                "dataset_rows": len(all_tasks),
                "selected_rows": len(tasks),
                "score_dataset": str(score_dataset_path),
                "jdt_command": args.jdt_server_cmd_json or "auto-discover",
            }
        )
        return target

    torch, tokenizer, model, device = load_model(args)
    java = args.java or os.environ.get("PROOFT5_JAVA") or shutil.which("java") or "java"
    java_home = Path(args.java_home or os.environ.get("PROOFT5_JAVA_HOME") or Path(java).resolve().parents[1])
    command = (
        json.loads(args.jdt_server_cmd_json)
        if args.jdt_server_cmd_json
        else discover_jdt_command(REPO_ROOT, java)
    )
    writer = CandidateWriter(target, resume=args.resume)
    workspace = REPO_ROOT / "tmp" / "repilot_jdt" / args.output_tag
    if workspace.exists() and not args.resume:
        raise FileExistsError(f"refusing to overwrite JDT workspace: {workspace}")
    workspace.mkdir(parents=True, exist_ok=True)
    with RepilotJdtClient(command, workspace, java_home, args.jdt_timeout) as jdt:
        for task in tasks:
            for rank in range(args.candidates):
                if args.resume and not writer.pending(task.index, rank):
                    continue
                source, trajectory = generate_one(
                    args, task, rank, torch, tokenizer, model, device, jdt
                )
                writer.write(task.index, rank, source, trajectory)
    writer.write_manifest(
        common_manifest(
            method="repilot_jdt_token_pruning",
            dataset_path=dataset_path,
            score_dataset_path=score_dataset_path,
            args=vars(args),
        )
        | {
            "model": args.model,
            "upstream_relation": (
                "task/model adapter around Repilot's modified Eclipse JDT "
                "newCompletion token-pruning mechanism; not the Defects4J repair CLI"
            ),
        }
    )
    print(f"saved candidates to {target}")
    return target


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Repilot-style JDT token-pruning adapter.")
    parser.add_argument("--dataset_json", required=True)
    parser.add_argument("--dataset_split", default="test")
    parser.add_argument("--score_task", required=True)
    parser.add_argument("--score_split", choices=["train", "valid", "test"], default="test")
    parser.add_argument("--output_tag", required=True)
    parser.add_argument("--model", default="")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--dtype", choices=["auto", "bf16", "fp16", "fp32"], default="bf16")
    parser.add_argument("--local_files_only", action="store_true")
    parser.add_argument("--lm_prompt_mode", choices=["raw_prefix", "instruction_suffix"], default="raw_prefix")
    parser.add_argument("--jdt_server_cmd_json", default="")
    parser.add_argument("--jdt_timeout", type=float, default=90.0)
    parser.add_argument("--java", default="")
    parser.add_argument("--java_home", default="")
    parser.add_argument("--candidates", type=int, default=10)
    parser.add_argument("--max_new_tokens", type=int, default=1024)
    parser.add_argument("--temperature", type=float, default=0.8)
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
