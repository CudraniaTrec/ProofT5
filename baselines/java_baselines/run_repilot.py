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
    extract_java_source,
    load_java_tasks,
    output_directory,
    select_tasks,
)
from baselines.java_baselines.hf_runtime import decoder_start_token_id, load_hf_runtime
from baselines.java_baselines.jdt_completion import (
    RepilotJdtClient,
    discover_jdt_command,
    trivially_feasible,
)


def load_model(args):
    runtime = load_hf_runtime(
        model_path=args.model,
        tokenizer_path=args.tokenizer,
        device=args.device,
        dtype=args.dtype,
        local_files_only=args.local_files_only,
        model_family=args.model_family,
    )
    return runtime.torch, runtime.tokenizer, runtime.model, runtime.device, runtime.family


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


def _decoded_delta(tokenizer, generated_ids, token_id):
    before = tokenizer.decode(
        generated_ids, skip_special_tokens=True, clean_up_tokenization_spaces=False
    )
    after = tokenizer.decode(
        generated_ids + [token_id],
        skip_special_tokens=True,
        clean_up_tokenization_spaces=False,
    )
    if after.startswith(before):
        return before, after, after[len(before) :]
    token = tokenizer.decode(
        [token_id], skip_special_tokens=False, clean_up_tokenization_spaces=False
    )
    return before, before + token, token


def _per_unit(seconds: float, count: int) -> float | None:
    return seconds / count if count else None


def _synchronize(torch, device) -> None:
    if getattr(device, "type", None) == "cuda":
        torch.cuda.synchronize(device)


def restore_repilot_support(base_weights, active_weights, rejected_indices):
    """Renormalization support after JDT rejects the current top-p set."""

    if active_weights.sum().item() > 0:
        return active_weights, False
    restored = base_weights.clone()
    restored[rejected_indices] = 0
    return restored, True


def longest_common_completion_prefix(continuations: list[str] | None) -> str | None:
    """Replicate Repilot artifact ``ACTIVE=1`` completion propagation."""

    if not continuations:
        return None
    prefix = continuations[0]
    for continuation in continuations[1:]:
        limit = min(len(prefix), len(continuation))
        index = 0
        while index < limit and prefix[index] == continuation[index]:
            index += 1
        prefix = prefix[:index]
        if not prefix:
            return None
    return prefix or None


def generate_one(args, task, rank, torch, tokenizer, model, device, jdt, model_family):
    _synchronize(torch, device)
    started = time.perf_counter()
    seed = args.seed + task.index * args.candidates + rank
    torch.manual_seed(seed)
    lm_text = task.prompt if model_family == "seq2seq" else model_prefix(
        tokenizer, task, args.lm_prompt_mode
    )
    encoded = tokenizer(
        lm_text, return_tensors="pt", max_length=args.max_input_tokens, truncation=True
    )
    encoded = {key: value.to(device) for key, value in encoded.items()}
    inputs = encoded["input_ids"]
    past = None
    encoder_outputs = None
    decoder_context_ids = []
    lm_seconds = 0.0
    if model_family == "seq2seq":
        _synchronize(torch, device)
        encoder_started = time.perf_counter()
        with torch.no_grad():
            encoder_outputs = model.get_encoder()(**encoded, return_dict=True)
        _synchronize(torch, device)
        lm_seconds += time.perf_counter() - encoder_started
        next_input = tokenizer(task.prompt, return_tensors="pt")["input_ids"].to(device)
        if not next_input.shape[-1]:
            next_input = torch.tensor(
                [[decoder_start_token_id(model, tokenizer)]], device=device
            )
        decoder_context_ids = next_input[0].tolist()
    else:
        next_input = inputs
    generated_ids = []
    generated_tokens = []
    rejected = []
    completion_queries = 0
    trivial_bypasses = 0
    support_expansions = 0
    active_completion = None
    active_completion_accepts = 0
    active_completion_rejections = 0
    active_completion_starts = 0
    jdt_query_seconds = 0.0
    jdt_document_seconds = 0.0
    if not args.decoder_control_no_jdt:
        document_started = time.perf_counter()
        jdt.open_document(task.prompt)
        jdt_document_seconds += time.perf_counter() - document_started
    effective_temperature = 0.0 if args.greedy_first and rank == 0 else args.temperature
    for step in range(args.max_new_tokens):
        _synchronize(torch, device)
        lm_started = time.perf_counter()
        with torch.no_grad():
            if model_family == "seq2seq":
                outputs = model(
                    encoder_outputs=encoder_outputs,
                    attention_mask=encoded.get("attention_mask"),
                    decoder_input_ids=next_input,
                    past_key_values=past,
                    use_cache=True,
                    return_dict=True,
                )
            else:
                outputs = model(
                    input_ids=next_input,
                    past_key_values=past,
                    use_cache=True,
                    return_dict=True,
                )
        _synchronize(torch, device)
        lm_seconds += time.perf_counter() - lm_started
        past = outputs.past_key_values
        logits = outputs.logits[:, -1, :].float()
        if effective_temperature > 0:
            logits = logits / effective_temperature
        top_scores, top_ids = torch.topk(logits[0], k=min(args.top_k, logits.shape[-1]))
        base_weights = torch.softmax(top_scores, dim=-1)
        weights = base_weights.clone()
        if effective_temperature > 0 and args.top_p < 1.0:
            remove = torch.cumsum(weights, dim=-1) > args.top_p
            remove[1:] = remove[:-1].clone()
            remove[0] = False
            weights[remove] = 0
        accepted_id = None
        accepted_token = ""
        rejected_local_indices = []
        while weights.sum().item() > 0:
            if effective_temperature > 0:
                local_index = int(torch.multinomial(weights, 1).item())
            else:
                local_index = int(torch.argmax(weights).item())
            token_id = int(top_ids[local_index].item())
            if token_id == tokenizer.eos_token_id:
                accepted_id, accepted_token = token_id, ""
                break
            decoded_ids = decoder_context_ids + generated_ids
            decoded, prospective, token = _decoded_delta(
                tokenizer, decoded_ids, token_id
            )
            source_prefix = task.prompt + decoded if model_family == "causal" else decoded
            prospective_source = (
                task.prompt + prospective if model_family == "causal" else prospective
            )
            active_accept = False
            active_reject = False
            if (
                not args.decoder_control_no_jdt
                and args.active_completion
                and active_completion is not None
            ):
                if active_completion.startswith(token):
                    active_accept = True
                elif not token.startswith(active_completion):
                    active_reject = True
            if args.decoder_control_no_jdt:
                feasible, continuations = True, None
                use_trivial_bypass = False
            elif active_accept:
                document_started = time.perf_counter()
                jdt.update_document(prospective_source)
                jdt_document_seconds += time.perf_counter() - document_started
                feasible, continuations = True, None
                active_completion = active_completion[len(token) :] or None
                active_completion_accepts += 1
                use_trivial_bypass = False
            elif active_reject:
                feasible, continuations = False, []
                active_completion_rejections += 1
                use_trivial_bypass = False
            else:
                use_trivial_bypass = (
                    args.jdt_query_policy == "upstream_trivial_bypass"
                    and trivially_feasible(token)
                )
            if args.decoder_control_no_jdt:
                pass
            elif use_trivial_bypass:
                document_started = time.perf_counter()
                jdt.update_document(prospective_source)
                jdt_document_seconds += time.perf_counter() - document_started
                feasible, continuations = True, None
                trivial_bypasses += 1
            else:
                completion_queries += 1
                query_started = time.perf_counter()
                feasible, continuations = jdt.token_feasible(source_prefix, token)
                jdt_query_seconds += time.perf_counter() - query_started
            if feasible:
                if (
                    not args.decoder_control_no_jdt
                    and args.active_completion
                    and not active_accept
                    and continuations
                ):
                    next_active = longest_common_completion_prefix(continuations)
                    if next_active:
                        active_completion = next_active
                        active_completion_starts += 1
                accepted_id, accepted_token = token_id, token
                break
            rejected.append({"step": step, "token_id": token_id, "token": token})
            rejected_local_indices.append(local_index)
            weights[local_index] = 0
            if weights.sum().item() == 0:
                # Upstream Repilot zeroes an infeasible token and renormalizes.
                # A top-p singleton must therefore expand to the remaining
                # untried top-k support instead of truncating the candidate.
                weights, expanded = restore_repilot_support(
                    base_weights, weights, rejected_local_indices
                )
                support_expansions += int(expanded)
        if accepted_id is None:
            break
        if accepted_id == tokenizer.eos_token_id:
            break
        generated_ids.append(accepted_id)
        generated_tokens.append(accepted_token)
        next_input = torch.tensor([[accepted_id]], device=device)
    generated_suffix = tokenizer.decode(
        generated_ids, skip_special_tokens=True, clean_up_tokenization_spaces=False
    )
    generated_text = tokenizer.decode(
        decoder_context_ids + generated_ids,
        skip_special_tokens=True,
        clean_up_tokenization_spaces=False,
    )
    source = extract_java_source(
        generated_text if model_family == "seq2seq" else task.prompt + generated_suffix
    )
    _synchronize(torch, device)
    elapsed_seconds = time.perf_counter() - started
    output_tokens = len(generated_ids)
    checker_seconds = jdt_query_seconds + jdt_document_seconds
    method = (
        "hf_matched_sampling_control"
        if args.decoder_control_no_jdt
        else "repilot_jdt_token_pruning"
    )
    return source, {
        "method": method,
        "task_id": task.task_id,
        "problem_index": task.index,
        "candidate_rank": rank,
        "seed": seed,
        "model": args.model,
        "tokenizer": args.tokenizer or args.model,
        "model_family": model_family,
        "lm_prompt_mode": args.lm_prompt_mode,
        "decoder_prefix_mode": (
            "forced_benchmark_prefix"
            if model_family == "seq2seq"
            else "causal_context"
        ),
        "temperature": effective_temperature,
        "top_p": args.top_p,
        "top_k": args.top_k,
        "generated_text": generated_text,
        "generated_suffix": generated_suffix,
        "generated_token_ids": generated_ids,
        "generated_tokens": generated_tokens,
        "rejected_tokens": rejected,
        "completion_queries": completion_queries,
        "jdt_query_policy": args.jdt_query_policy,
        "decoder_control_no_jdt": args.decoder_control_no_jdt,
        "trivial_bypasses": trivial_bypasses,
        "constraint_support_expansions": support_expansions,
        "active_completion_accepts": active_completion_accepts,
        "active_completion_rejections": active_completion_rejections,
        "active_completion_starts": active_completion_starts,
        "input_tokens": int(inputs.shape[-1]),
        "decoder_prefix_tokens": len(decoder_context_ids),
        "output_tokens": output_tokens,
        "lm_seconds": lm_seconds,
        "jdt_query_seconds": jdt_query_seconds,
        "jdt_document_seconds": jdt_document_seconds,
        "checker_seconds": checker_seconds,
        "non_lm_non_checker_seconds": max(
            0.0, elapsed_seconds - lm_seconds - checker_seconds
        ),
        "completion_queries_per_output_token": _per_unit(
            completion_queries, output_tokens
        ),
        "jdt_query_seconds_per_query": _per_unit(
            jdt_query_seconds, completion_queries
        ),
        "checker_seconds_per_output_token": _per_unit(
            checker_seconds, output_tokens
        ),
        "lm_seconds_per_output_token": _per_unit(lm_seconds, output_tokens),
        "elapsed_seconds_per_output_token": _per_unit(
            elapsed_seconds, output_tokens
        ),
        "elapsed_seconds": elapsed_seconds,
        "upstream_relation": (
            "matched Repilot decoder control with JDT disabled"
            if args.decoder_control_no_jdt
            else "adapts Repilot's modified-JDT newCompletion pruning policy"
        ),
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
        method = (
            "hf_matched_sampling_control"
            if args.decoder_control_no_jdt
            else "repilot_jdt_token_pruning"
        )
        print(
            {
                "method": method,
                "dataset_rows": len(all_tasks),
                "selected_rows": len(tasks),
                "score_dataset": str(score_dataset_path),
                "jdt_command": (
                    None
                    if args.decoder_control_no_jdt
                    else args.jdt_server_cmd_json or "auto-discover"
                ),
            }
        )
        return target

    run_started = time.perf_counter()
    model_initialization_started = time.perf_counter()
    torch, tokenizer, model, device, model_family = load_model(args)
    model_initialization_seconds = time.perf_counter() - model_initialization_started
    java = args.java or os.environ.get("PROOFT5_JAVA") or shutil.which("java") or "java"
    java_home = Path(args.java_home or os.environ.get("PROOFT5_JAVA_HOME") or Path(java).resolve().parents[1])
    command = None
    if not args.decoder_control_no_jdt:
        command = (
            json.loads(args.jdt_server_cmd_json)
            if args.jdt_server_cmd_json
            else discover_jdt_command(REPO_ROOT, java)
        )
    writer = CandidateWriter(target, resume=args.resume)
    workspace = REPO_ROOT / "tmp" / "repilot_jdt" / args.output_tag
    if not args.decoder_control_no_jdt:
        if workspace.exists() and not args.resume:
            raise FileExistsError(f"refusing to overwrite JDT workspace: {workspace}")
        workspace.mkdir(parents=True, exist_ok=True)

    def generate_all(jdt):
        nonlocal candidate_execution_seconds
        candidate_execution_started = time.perf_counter()
        for task in tasks:
            for rank in range(args.candidates):
                if args.resume and not writer.pending(task.index, rank):
                    continue
                source, trajectory = generate_one(
                    args, task, rank, torch, tokenizer, model, device, jdt, model_family
                )
                writer.write(task.index, rank, source, trajectory)
        candidate_execution_seconds = time.perf_counter() - candidate_execution_started

    jdt_startup_seconds = 0.0
    candidate_execution_seconds = 0.0
    if args.decoder_control_no_jdt:
        generate_all(None)
    else:
        jdt_startup_started = time.perf_counter()
        assert command is not None
        with RepilotJdtClient(command, workspace, java_home, args.jdt_timeout) as jdt:
            jdt_startup_seconds = time.perf_counter() - jdt_startup_started
            generate_all(jdt)
    run_wall_seconds = time.perf_counter() - run_started
    method = (
        "hf_matched_sampling_control"
        if args.decoder_control_no_jdt
        else "repilot_jdt_token_pruning"
    )
    writer.write_manifest(
        common_manifest(
            method=method,
            dataset_path=dataset_path,
            score_dataset_path=score_dataset_path,
            args=vars(args),
        )
        | {
            "model": args.model,
            "tokenizer": args.tokenizer or args.model,
            "model_family": model_family,
            "upstream_relation": (
                "matched Repilot sampling/forced-prefix decoder with JDT disabled"
                if args.decoder_control_no_jdt
                else "task/model adapter around Repilot's modified Eclipse JDT "
                "newCompletion token-pruning mechanism; not the Defects4J repair CLI"
            ),
            "timing_protocol": (
                "lm_seconds measures model forward calls; checker_seconds is JDT "
                "query plus document-update wall time"
            ),
            "active_completion": args.active_completion,
            "runtime_timing": {
                "model_initialization_seconds": model_initialization_seconds,
                "jdt_startup_seconds": jdt_startup_seconds,
                "candidate_execution_seconds": candidate_execution_seconds,
                "run_wall_seconds_before_manifest_write": run_wall_seconds,
            },
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
    parser.add_argument("--tokenizer", default="")
    parser.add_argument("--model_family", choices=["auto", "causal", "seq2seq"], default="auto")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--dtype", choices=["auto", "bf16", "fp16", "fp32"], default="bf16")
    parser.add_argument("--local_files_only", action="store_true")
    parser.add_argument("--lm_prompt_mode", choices=["raw_prefix", "instruction_suffix"], default="raw_prefix")
    parser.add_argument("--jdt_server_cmd_json", default="")
    parser.add_argument("--jdt_timeout", type=float, default=90.0)
    parser.add_argument(
        "--decoder_control_no_jdt",
        action="store_true",
        help="Run the identical sampling loop without JDT for matched attribution.",
    )
    parser.add_argument(
        "--jdt_query_policy",
        choices=["upstream_trivial_bypass", "every_token"],
        default="upstream_trivial_bypass",
        help=(
            "Repilot upstream bypasses punctuation/keywords; every_token is the "
            "stricter all-token JDT protocol requested for the new experiment."
        ),
    )
    parser.add_argument(
        "--active_completion",
        action=argparse.BooleanOptionalAction,
        default=False,
        help=(
            "Propagate the longest common continuation returned by JDT. This "
            "matches the artifact's optional ACTIVE=1 heuristic but is disabled "
            "for the sound paper-facing run because it falsely prunes known-correct "
            "Java training trajectories."
        ),
    )
    parser.add_argument("--java", default="")
    parser.add_argument("--java_home", default="")
    parser.add_argument("--candidates", type=int, default=10)
    parser.add_argument("--max_new_tokens", type=int, default=1024)
    parser.add_argument("--max_input_tokens", type=int, default=1024)
    parser.add_argument("--temperature", type=float, default=0.8)
    parser.add_argument(
        "--greedy_first",
        action="store_true",
        help="Use greedy decoding for rank 0 and sampling for later candidates.",
    )
    parser.add_argument("--top_k", type=int, default=50)
    parser.add_argument("--top_p", type=float, default=0.95)
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
