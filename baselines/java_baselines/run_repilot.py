from __future__ import annotations

import argparse
import json
import os
import re
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
    finalize_java_compilation_unit,
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


def useful_proactive_completion(text: str, current_source: str) -> bool:
    """Reject punctuation/numeric IDE prefixes before direct ACTIVE insertion.

    JDT legitimately returns common prefixes such as ``("``, ``1`` or a
    repeated type name while the file is incomplete.  Those prefixes are
    useful feasibility hints but are not the identifier completion that
    Repilot's ACTIVE mechanism is intended to insert directly.  Restricting
    proactive insertion to a complete identifier/qualified-name prefix also
    prevents repeatedly appending the same stale proposal after a malformed
    model continuation.
    """
    if not text or text != text.strip() or len(text) < 1:
        return False
    if not re.fullmatch(
        r"[A-Za-z_$][A-Za-z0-9_$]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*)*\(?",
        text,
    ):
        return False
    return not current_source.endswith(text)


def choose_active_completion(
    continuations: list[str], mode: str, current_source: str
) -> str | None:
    """Select the IDE continuation used by Repilot ACTIVE.

    The paper uses the longest common prefix (LCP), which is the sound choice
    when proposals are exhaustive.  In the standalone JDT adapter the LCP is
    often empty because unrelated keyword proposals are returned alongside a
    useful method/type proposal.  ``proactive_top`` keeps the LCP first and,
    only when it is empty, uses the highest-ranked identifier/method proposal
    from JDT.  This is deliberately opt-in and never applies punctuation or
    literals, so the default paper-faithful path is unchanged.
    """
    common = longest_common_completion_prefix(continuations)
    if common:
        return common
    if mode != "proactive_top":
        return None
    for candidate in continuations:
        if useful_proactive_completion(candidate, current_source):
            return candidate
    return None


def repilot_method_name(args) -> str:
    if args.decoder_control_no_jdt:
        return "hf_matched_sampling_control"
    active_policy = getattr(args, "active_completion_policy", "upstream")
    active_mode = getattr(args, "active_completion_mode", "hint")
    if args.active_completion and active_policy == "safe":
        if getattr(args, "ide_best_effort", False):
            return (
                "repilot_jdt_ide_active_proactive_safe"
                if active_mode in {"proactive", "proactive_top"}
                else "repilot_jdt_ide_active_safe"
            )
        return (
            "repilot_jdt_active_proactive_safe"
            if active_mode in {"proactive", "proactive_top"}
            else "repilot_jdt_active_safe"
        )
    if args.active_completion:
        return (
            "repilot_jdt_active_proactive_upstream"
            if active_mode in {"proactive", "proactive_top"}
            else "repilot_jdt_active_upstream"
        )
    if getattr(args, "ide_best_effort", False):
        return "repilot_jdt_ide_token_pruning"
    return "repilot_jdt_token_pruning"


def generate_one(
    args,
    task,
    rank,
    torch,
    tokenizer,
    model,
    device,
    jdt,
    model_family,
):
    active_completion_policy = getattr(
        args, "active_completion_policy", "upstream"
    )
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
    seq2seq_force_prefix = (
        model_family == "seq2seq"
        and getattr(args, "seq2seq_decoder_mode", "forced_prefix") == "forced_prefix"
    )
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
        if seq2seq_force_prefix:
            next_input = tokenizer(task.prompt, return_tensors="pt")["input_ids"].to(device)
            if not next_input.shape[-1]:
                next_input = torch.tensor(
                    [[decoder_start_token_id(model, tokenizer)]], device=device
                )
        else:
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
    active_completion_fallbacks = 0
    active_completion_starts = 0
    active_completion_insertions = 0
    active_completion_inserted_tokens = 0
    active_completion_inserted_texts = []
    completion_cache_hits_before = (
        getattr(jdt, "completion_cache_hits", 0)
        if jdt is not None
        else 0
    )
    jdt_query_seconds = 0.0
    jdt_document_seconds = 0.0
    if not args.decoder_control_no_jdt:
        document_started = time.perf_counter()
        initial_document = (
            task.prompt
            if model_family != "seq2seq" or seq2seq_force_prefix
            else ""
        )
        jdt.open_document(initial_document)
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
                    if active_completion_policy == "upstream":
                        active_reject = True
                    else:
                        # JDT's completion list is a useful affirmative hint,
                        # but it is not guaranteed to be exhaustive. In the
                        # safe mode a divergent token falls back to the normal
                        # JDT/trivial-feasibility path instead of being
                        # rejected solely because it was absent from a
                        # possibly incomplete proposal list.
                        active_completion = None
                        active_completion_fallbacks += 1
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
            if args.decoder_control_no_jdt or active_accept or active_reject:
                # ``feasible`` was already decided by the matched control or
                # ACTIVE branch above.  In particular, ACTIVE acceptance must
                # not issue a duplicate JDT request for the same token.
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
                next_active = None
                if (
                    not args.decoder_control_no_jdt
                    and args.active_completion
                    and not active_accept
                    and continuations
                ):
                    current_source_for_completion = (
                        task.prompt
                        + tokenizer.decode(
                            generated_ids,
                            skip_special_tokens=True,
                            clean_up_tokenization_spaces=False,
                        )
                        if model_family == "causal"
                        else tokenizer.decode(
                            decoder_context_ids + generated_ids,
                            skip_special_tokens=True,
                            clean_up_tokenization_spaces=False,
                        )
                    )
                    next_active = choose_active_completion(
                        continuations,
                        getattr(args, "active_completion_mode", "hint"),
                        current_source_for_completion,
                    )
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

        # The paper's ACTIVE mode does not merely use the completion as a
        # filter: it aligns the common completion prefix to the LM vocabulary
        # and inserts the resulting token sequence without another LM sample.
        # The old adapter only carried the prefix as a hint, which preserved
        # the base model's sampling distribution and therefore could not
        # improve accuracy.  In proactive mode we perform the direct
        # insertion and deliberately recompute the decoder cache on the next
        # iteration.  Recomputing is slower but unambiguous for both the
        # seq2seq checkpoint used in the formal run and causal controls.
        if (
            getattr(args, "active_completion_mode", "hint") in {
                "proactive",
                "proactive_top",
            }
            and active_completion
            and not args.decoder_control_no_jdt
        ):
            active_text = active_completion
            current_source = (
                task.prompt
                + tokenizer.decode(
                    generated_ids,
                    skip_special_tokens=True,
                    clean_up_tokenization_spaces=False,
                )
                if model_family == "causal"
                else tokenizer.decode(
                    decoder_context_ids + generated_ids,
                    skip_special_tokens=True,
                    clean_up_tokenization_spaces=False,
                )
            )
            if not useful_proactive_completion(active_text, current_source):
                active_completion = None
                active_text = None
            if active_text is None:
                # Keep the completion as a normal hint only.  The next outer
                # iteration will let the model choose punctuation, literals,
                # or any other token after the JDT feasibility check.
                pass
            else:
                active_ids = tokenizer.encode(active_text, add_special_tokens=False)
                special_ids = {
                    value
                    for value in (
                        getattr(tokenizer, "eos_token_id", None),
                        getattr(tokenizer, "pad_token_id", None),
                        getattr(tokenizer, "bos_token_id", None),
                    )
                    if value is not None
                }
                active_ids = [
                    token_id for token_id in active_ids if token_id not in special_ids
                ]
                if active_ids:
                    active_decoded_ids = decoder_context_ids + generated_ids
                    for active_id in active_ids:
                        _, _, active_token = _decoded_delta(
                            tokenizer, active_decoded_ids, int(active_id)
                        )
                        generated_ids.append(int(active_id))
                        generated_tokens.append(active_token)
                        active_decoded_ids.append(int(active_id))
                    active_completion_insertions += 1
                    active_completion_inserted_tokens += len(active_ids)
                    active_completion_inserted_texts.append(active_text)
                    active_completion = None
                    active_source = (
                        task.prompt
                        + tokenizer.decode(
                            generated_ids,
                            skip_special_tokens=True,
                            clean_up_tokenization_spaces=False,
                        )
                        if model_family == "causal"
                        else tokenizer.decode(
                            decoder_context_ids + generated_ids,
                            skip_special_tokens=True,
                            clean_up_tokenization_spaces=False,
                        )
                    )
                    document_started = time.perf_counter()
                    jdt.update_document(active_source)
                    jdt_document_seconds += time.perf_counter() - document_started
                    past = None
                    next_input = torch.tensor(
                        [
                            (
                                inputs[0].tolist() + generated_ids
                                if model_family == "causal"
                                else decoder_context_ids + generated_ids
                            )
                        ],
                        device=device,
                    )
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
    java_postprocess = "disabled"
    if getattr(args, "java_safe_completion", False):
        # The benchmark expects a complete compilation unit, whereas a
        # decoder can stop immediately after the target method.  This opt-in
        # adapter postprocess closes only a class whose method has already
        # closed; it does not invent a method body or alter JDT pruning.
        source, java_postprocess = finalize_java_compilation_unit(
            source, len(task.prompt) if seq2seq_force_prefix else 0
        )
    _synchronize(torch, device)
    elapsed_seconds = time.perf_counter() - started
    output_tokens = len(generated_ids)
    checker_seconds = jdt_query_seconds + jdt_document_seconds
    method = repilot_method_name(args)
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
            if seq2seq_force_prefix
            else "decoder_start_only_full_output"
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
        "completion_cache_hits": (
            getattr(jdt, "completion_cache_hits", 0) - completion_cache_hits_before
            if jdt is not None
            else 0
        ),
        "jdt_query_policy": args.jdt_query_policy,
        "decoder_control_no_jdt": args.decoder_control_no_jdt,
        "trivial_bypasses": trivial_bypasses,
        "constraint_support_expansions": support_expansions,
        "active_completion_accepts": active_completion_accepts,
        "active_completion_rejections": active_completion_rejections,
        "active_completion_fallbacks": active_completion_fallbacks,
        "active_completion_starts": active_completion_starts,
        "active_completion_mode": getattr(args, "active_completion_mode", "hint"),
        "active_completion_insertions": active_completion_insertions,
        "active_completion_inserted_tokens": active_completion_inserted_tokens,
        "active_completion_inserted_texts": active_completion_inserted_texts,
        "active_completion_policy": active_completion_policy,
        "ide_best_effort": getattr(args, "ide_best_effort", False),
        "jdt_join_completion": getattr(args, "ide_join_completion", False),
        "jdt_completion_timeout_ms": getattr(args, "completion_timeout_ms", None),
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
        "java_safe_completion": getattr(args, "java_safe_completion", False),
        "java_postprocess": java_postprocess,
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
        method = repilot_method_name(args)
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
            else discover_jdt_command(
                REPO_ROOT,
                java,
                join_completion=args.ide_join_completion,
                completion_timeout_ms=(
                    args.completion_timeout_ms if args.ide_best_effort else None
                ),
            )
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
                    args,
                    task,
                    rank,
                    torch,
                    tokenizer,
                    model,
                    device,
                    jdt,
                    model_family,
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
    method = repilot_method_name(args)
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
                else (
                    "Repilot modified-JDT newCompletion with full IDE completion "
                    "capabilities and extended timeout; safe ACTIVE is separately recorded"
                    if args.ide_best_effort
                    else "task/model adapter around Repilot's modified Eclipse JDT "
                    "newCompletion token-pruning mechanism; not the Defects4J repair CLI"
                )
            ),
            "timing_protocol": (
                "lm_seconds measures model forward calls; checker_seconds is JDT "
                "query plus document-update wall time"
            ),
            "active_completion": args.active_completion,
            "active_completion_policy": args.active_completion_policy,
            "active_completion_mode": args.active_completion_mode,
            "ide_best_effort": args.ide_best_effort,
            "jdt_join_completion": args.ide_join_completion,
            "jdt_completion_timeout_ms": args.completion_timeout_ms,
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
    parser.add_argument(
        "--seq2seq_decoder_mode",
        choices=["forced_prefix", "full_output"],
        default="forced_prefix",
        help=(
            "For T5-style checkpoints, either teacher-force the benchmark Java "
            "prefix (the frozen contract) or decode the model's complete target "
            "from its decoder-start token."
        ),
    )
    parser.add_argument("--jdt_server_cmd_json", default="")
    parser.add_argument("--jdt_timeout", type=float, default=90.0)
    parser.add_argument(
        "--ide_best_effort",
        action="store_true",
        help=(
            "Use Repilot's modified JDT with full completion capabilities and "
            "the configured completion timeout. This only changes the IDE/JDT "
            "path; it does not import SynCode or another syntax checker."
        ),
    )
    parser.add_argument(
        "--completion_timeout_ms",
        type=int,
        default=5000,
        help="JDT completion request timeout used by --ide_best_effort.",
    )
    parser.add_argument(
        "--ide_join_completion",
        action="store_true",
        help=(
            "Also wait for all JDT lifecycle jobs before every completion. "
            "This is a strict, very slow diagnostic; leave it off for the "
            "formal benchmark rerun."
        ),
    )
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
    parser.add_argument(
        "--active_completion_policy",
        choices=["upstream", "safe"],
        default="upstream",
        help=(
            "When ACTIVE completion is enabled, upstream rejects any token "
            "outside the returned proposal prefix. The safe policy treats the "
            "prefix as an affirmative hint and rechecks divergent tokens with "
            "JDT; this avoids relying on proposal-list exhaustiveness."
        ),
    )
    parser.add_argument(
        "--active_completion_mode",
        choices=["hint", "proactive", "proactive_top"],
        default="hint",
        help=(
            "ACTIVE handling: hint keeps the completion as a token-level hint; "
            "proactive aligns and inserts the common completion prefix directly, "
            "matching Repilot Algorithm 3 at higher LM/cache cost; proactive_top "
            "also permits JDT's highest-ranked identifier/method proposal when "
            "the common prefix is empty."
        ),
    )
    parser.add_argument("--java", default="")
    parser.add_argument("--java_home", default="")
    parser.add_argument(
        "--java_safe_completion",
        action=argparse.BooleanOptionalAction,
        default=False,
        help=(
            "Close a completed Java method's class brace at serialization time. "
            "Opt-in adapter postprocess; frozen rows remain unchanged."
        ),
    )
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
