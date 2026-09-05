from __future__ import annotations

import argparse
import contextlib
import types
import re
import signal
import sys
import time
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from baselines.java_baselines.common import (
    CandidateWriter,
    align_tasks_to_score,
    common_manifest,
    extract_java_source,
    load_java_tasks,
    output_directory,
    select_tasks,
)
from baselines.java_baselines.hf_runtime import decoder_start_token_id, load_hf_runtime
from baselines.java_baselines.syncode_cache_guard import (
    finalize_mask_store,
    prepare_mask_store,
)


class CandidateGenerationTimeout(BaseException):
    """Hard candidate deadline that upstream parser `except Exception` cannot swallow."""

    pass


class SynCodeParserFailure(BaseException):
    """Fail closed after grammar-mask overapproximation admits an invalid token."""

    def __init__(self, input_ids):
        super().__init__("SynCode incremental parser rejected the accepted prefix")
        self.input_ids = input_ids.detach().clone()


def restore_ignored_whitespace_tokens_in_mask_store(grammar_engine, tokenizer, torch) -> int:
    """Repair an upstream grammar-mask hole for standalone ignored whitespace.

    SynCode's Java parser explicitly accepts ``WS`` between terminals, but its
    precomputed transition table can omit tokenizer tokens consisting only of a
    newline (notably T5Gemma token 107).  Unioning these tokens is sound only
    when the current parse result has an ignored-WS transition; strings and
    other lexical interiors therefore remain constrained.
    """

    mask_store = grammar_engine.dfa_mask_store
    whitespace_ids = [
        token_id
        for token_id in range(len(mask_store._vocab))
        if (piece := tokenizer.decode([token_id], skip_special_tokens=True))
        and piece.isspace()
    ]
    if not whitespace_ids:
        return 0
    whitespace_mask = torch.zeros(len(mask_store._vocab), dtype=torch.bool)
    whitespace_mask[whitespace_ids] = True
    original = mask_store.get_accept_mask

    def get_accept_mask_with_ignored_whitespace(self, result, get_list=False):
        mask = original(result, get_list=False)
        states = list(self.get_fsm_states(result))
        whitespace_allowed = False
        for sequence in result.accept_sequences:
            if len(sequence) >= 1 and sequence[0] == "WS":
                whitespace_allowed = True
                break
            if len(sequence) >= 2 and sequence[1] == "WS":
                if any(
                    state.terminal == sequence[0] and self._fsms.is_final(state)
                    for state in states
                ):
                    whitespace_allowed = True
                    break
        if whitespace_allowed:
            mask = mask | whitespace_mask
        if get_list:
            return self._get_tokens_list(mask)
        return mask

    mask_store.get_accept_mask = types.MethodType(
        get_accept_mask_with_ignored_whitespace, mask_store
    )
    return len(whitespace_ids)


_JAVA_REFERENCE_CAST = re.compile(
    r"\(\s*([A-Za-z_$][\w$]*(?:\s*\.\s*[A-Za-z_$][\w$]*)*"
    r"(?:\s*<[^()]*>)?(?:\s*\[\s*\])*)\s*\)"
)
_JAVA_PRIMITIVE_TYPES = {
    "boolean",
    "byte",
    "char",
    "double",
    "float",
    "int",
    "long",
    "short",
}


def java_sound_overapprox_grammar(grammar_text: str) -> tuple[str, int]:
    """Remove the upstream Java CFG's unsound cast ambiguity.

    With Lark's basic lexer, the upstream grammar resolves ``(Integer) value``
    as a possible parenthesized lambda parameter and then masks ``value``.  The
    parser view below elides completed casts, so the cast production must not
    compete with ordinary parenthesized expressions.  This deliberately makes
    the adapter more permissive; it cannot claim that casts themselves are
    syntax-checked.
    """

    needle = ' | cast_expression'
    count = grammar_text.count(needle)
    if count != 1:
        raise ValueError(
            "expected exactly one cast_expression alternative in SynCode Java grammar, "
            f"found {count}"
        )
    return grammar_text.replace(needle, ""), count


def normalize_java_sound_overapprox_parser_view(
    source: str,
) -> tuple[str, dict[str, int]]:
    """Create a conservative parser-only view for SynCode's incomplete Java CFG.

    The upstream basic lexer always gives ``>>``/``>>>`` to shift tokens, even
    when the characters close nested generic arguments.  We split only closers
    inside a type argument opened immediately after an upper-case Java type
    name, leaving actual shift operators unchanged.  Completed primitive or
    reference casts are replaced by spaces because the upstream cast/lambda
    ambiguity otherwise rejects known-correct operands.  Strings and comments
    are never rewritten.  Model input and emitted source remain byte-for-byte
    unchanged.
    """

    output: list[str] = []
    code_mask: list[bool] = []
    generic_depth = 0
    generic_closer_splits = 0
    index = 0
    state = "code"
    while index < len(source):
        char = source[index]
        following = source[index + 1] if index + 1 < len(source) else ""
        if state == "code":
            if char == '"':
                state = "string"
            elif char == "'":
                state = "character"
            elif char == "/" and following == "/":
                output.extend((char, following))
                code_mask.extend((False, False))
                state = "line_comment"
                index += 2
                continue
            elif char == "/" and following == "*":
                output.extend((char, following))
                code_mask.extend((False, False))
                state = "block_comment"
                index += 2
                continue
            elif char == "<":
                preceding = re.search(r"([A-Za-z_$][\w$]*)\s*$", "".join(output))
                if preceding and preceding.group(1)[0].isupper():
                    generic_depth += 1
            elif char == ">" and generic_depth:
                if index > 0 and source[index - 1] == ">":
                    output.append(" ")
                    code_mask.append(True)
                    generic_closer_splits += 1
                generic_depth -= 1
            output.append(char)
            code_mask.append(True)
            index += 1
            continue

        output.append(char)
        code_mask.append(False)
        if state in {"string", "character"}:
            if char == "\\" and index + 1 < len(source):
                output.append(source[index + 1])
                code_mask.append(False)
                index += 2
                continue
            if (state == "string" and char == '"') or (
                state == "character" and char == "'"
            ):
                state = "code"
        elif state == "line_comment" and char in "\r\n":
            state = "code"
        elif state == "block_comment" and char == "*" and following == "/":
            output.append(following)
            code_mask.append(False)
            state = "code"
            index += 2
            continue
        index += 1

    normalized = "".join(output)
    cast_elisions = 0
    for match in reversed(list(_JAVA_REFERENCE_CAST.finditer(normalized))):
        if not all(code_mask[match.start() : match.end()]):
            continue
        type_spelling = match.group(1)
        identifiers = re.findall(r"[A-Za-z_$][\w$]*", type_spelling)
        if not identifiers:
            continue
        final_type = identifiers[-1]
        if final_type not in _JAVA_PRIMITIVE_TYPES and not final_type[0].isupper():
            continue
        replacement = "".join(
            "\n" if char == "\n" else "\r" if char == "\r" else " "
            for char in match.group(0)
        )
        normalized = normalized[: match.start()] + replacement + normalized[match.end() :]
        cast_elisions += 1
    return normalized, {
        "generic_closer_splits": generic_closer_splits,
        "cast_elisions": cast_elisions,
    }


def finalize_syncode_java_source(source: str, prompt_length: int) -> tuple[str, str]:
    """Stop at the first complete class, or close a completed target method.

    SynCode's own code-evaluation path backs unfinished generations up to a
    recorded function end.  The generic upstream helper is Python/Go-oriented,
    so this adapter uses Java brace structure while ignoring protected text.
    It never invents a method body: a closing class brace is added only after
    the generated target method has already closed.
    """

    depth = 0
    seen_brace = False
    state = "code"
    index = 0
    method_close = None
    while index < len(source):
        char = source[index]
        following = source[index + 1] if index + 1 < len(source) else ""
        if state == "code":
            if char == '"':
                state = "string"
            elif char == "'":
                state = "character"
            elif char == "/" and following == "/":
                state = "line_comment"
                index += 2
                continue
            elif char == "/" and following == "*":
                state = "block_comment"
                index += 2
                continue
            elif char == "{":
                depth += 1
                seen_brace = True
            elif char == "}":
                previous_depth = depth
                depth = max(0, depth - 1)
                if index >= prompt_length and previous_depth == 2 and depth == 1:
                    method_close = index + 1
                if index >= prompt_length and seen_brace and depth == 0:
                    return source[: index + 1], "complete_unit_truncation"
            index += 1
            continue
        if state in {"string", "character"}:
            if char == "\\" and index + 1 < len(source):
                index += 2
                continue
            if (state == "string" and char == '"') or (
                state == "character" and char == "'"
            ):
                state = "code"
        elif state == "line_comment" and char in "\r\n":
            state = "code"
        elif state == "block_comment" and char == "*" and following == "/":
            state = "code"
            index += 2
            continue
        index += 1
    if method_close is not None:
        return source[:method_close].rstrip() + "\n}", "method_close_class_completion"
    return source, "no_safe_completion"


class JavaCompilationUnitStoppingCriteria:
    """Stop generation as soon as the benchmark's Java class is complete."""

    def __init__(self, tokenizer, prompt_length: int):
        self.tokenizer = tokenizer
        self.prompt_length = prompt_length
        self.triggered = False

    def __call__(self, input_ids, scores, **kwargs):
        del scores, kwargs
        decoded = self.tokenizer.decode(
            input_ids[0],
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False,
        )
        source = extract_java_source(decoded)
        _, policy = finalize_syncode_java_source(source, self.prompt_length)
        self.triggered = policy == "complete_unit_truncation"
        return input_ids.new_tensor([self.triggered], dtype=self._bool_dtype(input_ids))

    @staticmethod
    def _bool_dtype(input_ids):
        import torch

        del input_ids
        return torch.bool


def _per_unit(seconds: float, count: int) -> float | None:
    return seconds / count if count else None


def normalize_java_nested_generic_prefix(prefix: str) -> tuple[str, int]:
    """Split nested-generic closers in the fixed benchmark method signature."""

    replacements = 0
    method_body_open = prefix.rfind("{")
    if method_body_open < 0:
        return prefix, replacements
    comment_end = prefix.rfind("*/", 0, method_body_open)
    if comment_end >= 0:
        signature_start = comment_end + 2
    else:
        signature_start = prefix.rfind("\n", 0, method_body_open) + 1

    def split_closers(match: re.Match[str]) -> str:
        nonlocal replacements
        replacements += 1
        return " ".join(match.group(0))

    signature = prefix[signature_start:method_body_open]
    normalized = re.sub(r">{2,}", split_closers, signature)
    return (
        prefix[:signature_start] + normalized + prefix[method_body_open:],
        replacements,
    )


class IncrementalPartialOutputDecoder:
    """Avoid re-decoding the full generated token prefix at every SynCode step.

    SynCode's parser still validates the complete Java prefix.  This cache only replaces
    the quadratic GPU-to-CPU token-id copy and byte-token decoding in
    ``GrammarConstrainer._get_partial_outputs``; it does not cache parser decisions or
    change the grammar mask.
    """

    def __init__(self, grammar_engine):
        self.grammar_engine = grammar_engine
        self.sound_overapprox = False
        self.reset()

    def reset(self) -> None:
        batch_size = self.grammar_engine.batch_size
        self._token_ids = [[] for _ in range(batch_size)]
        self._decoded = [b"" for _ in range(batch_size)]
        self.cache_hits = 0
        self.full_decodes = 0
        self.fixed_prefix = ""
        self.parser_prefix = ""
        self.prefix_rewrite_applied_calls = 0
        self.generic_closer_splits = 0
        self.cast_elisions = 0

    def set_fixed_prefix(self, fixed_prefix: str, parser_prefix: str) -> None:
        self.fixed_prefix = fixed_prefix
        self.parser_prefix = parser_prefix

    def set_sound_overapprox(self, enabled: bool) -> None:
        self.sound_overapprox = enabled

    def __call__(self, input_ids):
        start_from = self.grammar_engine.start_from or 0
        outputs = []
        for idx in range(len(input_ids)):
            previous = self._token_ids[idx]
            current_length = int(input_ids.shape[1]) - start_from
            if current_length == len(previous) + 1:
                delta = input_ids[idx, start_from + len(previous) :].tolist()
                self._decoded[idx] += self.grammar_engine.byte_tokenizer.decode(
                    delta, skip_special_tokens=True
                )
                current = previous + delta
                self.cache_hits += 1
            else:
                current = input_ids[idx, start_from:].tolist()
                self._decoded[idx] = self.grammar_engine.byte_tokenizer.decode(
                    current, skip_special_tokens=True
                )
                self.full_decodes += 1
            self._token_ids[idx] = current
            partial_output, remainder = self.grammar_engine._bytes_to_string(
                self._decoded[idx]
            )
            if (
                self.fixed_prefix
                and self.parser_prefix != self.fixed_prefix
                and partial_output.startswith(self.fixed_prefix)
            ):
                partial_output = self.parser_prefix + partial_output[len(self.fixed_prefix) :]
                self.prefix_rewrite_applied_calls += 1
            if self.sound_overapprox:
                partial_output, rewrites = normalize_java_sound_overapprox_parser_view(
                    partial_output
                )
                self.generic_closer_splits += rewrites["generic_closer_splits"]
                self.cast_elisions += rewrites["cast_elisions"]
            outputs.append((partial_output, remainder))
        return outputs


class TimedSyncodeLogitsProcessor:
    """Measure SynCode constraint cost separately from the rest of generation."""

    def __init__(
        self,
        processor,
        torch,
        device,
        incremental_input_decode: bool = True,
        fail_closed_on_parse_error: bool = False,
    ):
        self.processor = processor
        self.torch = torch
        self.device = device
        self.fail_closed_on_parse_error = fail_closed_on_parse_error
        self.grammar_engine = processor.grammar_engine
        self.incremental_decoder = None
        if incremental_input_decode:
            self.incremental_decoder = IncrementalPartialOutputDecoder(
                self.grammar_engine
            )
            self.grammar_engine._get_partial_outputs = self.incremental_decoder
        self.reset()

    def reset(self) -> None:
        self.processor.reset()
        self.constraint_calls = 0
        self.constraint_seconds = 0.0
        if self.incremental_decoder is not None:
            self.incremental_decoder.reset()

    def __call__(self, input_ids, scores):
        self.constraint_calls += 1
        self._synchronize()
        started = time.perf_counter()
        try:
            result = self.processor(input_ids, scores)
            if self.fail_closed_on_parse_error and self.grammar_engine.parse_failed:
                raise SynCodeParserFailure(input_ids)
            return result
        finally:
            self._synchronize()
            self.constraint_seconds += time.perf_counter() - started

    def _synchronize(self) -> None:
        if getattr(self.device, "type", None) == "cuda":
            self.torch.cuda.synchronize(self.device)

    def set_fixed_parser_prefix(self, fixed_prefix: str, parser_prefix: str) -> None:
        if self.incremental_decoder is not None:
            self.incremental_decoder.set_fixed_prefix(fixed_prefix, parser_prefix)

    def set_sound_overapprox(self, enabled: bool) -> None:
        if self.incremental_decoder is None and enabled:
            raise ValueError("Java sound-overapprox parser view requires incremental decoding")
        if self.incremental_decoder is not None:
            self.incremental_decoder.set_sound_overapprox(enabled)


@contextlib.contextmanager
def candidate_time_limit(seconds: float):
    if seconds <= 0:
        yield
        return
    previous = signal.getsignal(signal.SIGALRM)

    def raise_timeout(signum, frame):
        del signum, frame
        raise CandidateGenerationTimeout(
            f"SynCode candidate exceeded {seconds:.1f} seconds"
        )

    signal.signal(signal.SIGALRM, raise_timeout)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def load_runtime(args):
    try:
        from syncode import Grammar, SyncodeLogitsProcessor
    except ImportError as exc:
        raise RuntimeError(
            "SynCode runtime is missing. Run baselines/java_baselines/bootstrap_envs.sh "
            "and use prooft5-syncode-py312 for causal models or "
            "prooft5-syncode-t5gemma-py312 for T5Gemma2."
        ) from exc

    runtime = load_hf_runtime(
        model_path=args.model,
        tokenizer_path=args.tokenizer,
        device=args.device,
        dtype=args.dtype,
        local_files_only=args.local_files_only,
        model_family=args.model_family,
    )
    torch, tokenizer, model, device = (
        runtime.torch,
        runtime.tokenizer,
        runtime.model,
        runtime.device,
    )
    grammar = Grammar(args.grammar)
    if args.java_sound_overapprox:
        if args.grammar != "java":
            raise ValueError("--java_sound_overapprox requires --grammar java")
        grammar_text, _ = java_sound_overapprox_grammar(grammar.ebnf)
        grammar = Grammar(grammar_text)
    cache_path, metadata_path, cache_metadata = prepare_mask_store(
        tokenizer, grammar, args.syncode_mode, args.rebuild_mask_store
    )
    upstream_processor = SyncodeLogitsProcessor(
        grammar=grammar,
        tokenizer=tokenizer,
        use_cache=not args.rebuild_mask_store,
        parse_output_only=False,
        num_samples=1,
        dev_mode=args.dev_mode,
        parser=args.parser,
        mode=args.syncode_mode,
    )
    ignored_whitespace_token_repairs = restore_ignored_whitespace_tokens_in_mask_store(
        upstream_processor.grammar_engine, tokenizer, torch
    )
    processor = TimedSyncodeLogitsProcessor(
        upstream_processor,
        torch,
        device,
        incremental_input_decode=not args.disable_incremental_input_decode,
        fail_closed_on_parse_error=args.fail_closed_on_parse_error,
    )
    processor.ignored_whitespace_token_repairs = ignored_whitespace_token_repairs
    processor.set_sound_overapprox(args.java_sound_overapprox)
    finalize_mask_store(cache_path, metadata_path, cache_metadata)
    return torch, tokenizer, model, device, processor, runtime.family


def tokenize_prompt(tokenizer, task, device, model_family):
    encoded = tokenizer(task.prompt, return_tensors="pt")
    encoded = {key: value.to(device) for key, value in encoded.items()}
    decoder_prefix_tokens = 0
    if model_family == "seq2seq":
        decoder_input_ids = tokenizer(task.prompt, return_tensors="pt")[
            "input_ids"
        ].to(device)
        encoded["decoder_input_ids"] = decoder_input_ids
        decoder_prefix_tokens = int(decoder_input_ids.shape[-1])
    return encoded, decoder_prefix_tokens


def materialize_syncode_candidate(
    task, generated_text: str, model_family: str = "causal"
) -> str:
    if model_family == "seq2seq":
        return extract_java_source(generated_text)
    return task.prompt + generated_text


def select_candidate_ranks(candidate_count: int, specification: str) -> list[int]:
    ranks = list(range(candidate_count))
    if not specification:
        return ranks
    selected = [int(value) for value in specification.split(",") if value.strip()]
    if len(selected) != len(set(selected)):
        raise ValueError("candidate ranks must be unique")
    invalid = [rank for rank in selected if rank < 0 or rank >= candidate_count]
    if invalid:
        raise ValueError(f"candidate ranks outside [0, {candidate_count}): {invalid}")
    return selected


def _restore_sampling_support(base_weights, active_weights, rejected_indices):
    if active_weights.sum().item() > 0:
        return active_weights, False
    restored = base_weights.clone()
    restored[rejected_indices] = 0
    return restored, True


def generate_proposal_preserving_candidate(
    args, task, rank, torch, tokenizer, model, device, processor, model_family
):
    """Apply SynCode as rejection after the ordinary model proposes a token.

    Upstream ``generate`` masks logits before multinomial sampling.  Although
    that is distributionally correct constrained sampling, it changes every
    fixed-seed trajectory after renormalization and can lose a successful
    finite-budget sample without any false prune.  This matched adaptation uses
    the exact ordinary proposal distribution and resamples only after SynCode
    rejects the proposed token, matching the Repilot control semantics.
    """

    processor._synchronize()
    started = time.perf_counter()
    seed = args.seed + task.index * args.candidates + rank
    torch.manual_seed(seed)
    encoded = tokenizer(
        task.prompt,
        return_tensors="pt",
        max_length=args.max_input_tokens,
        truncation=True,
    )
    encoded = {key: value.to(device) for key, value in encoded.items()}
    inputs = encoded["input_ids"]
    past = None
    encoder_outputs = None
    decoder_context_ids: list[int] = []
    lm_seconds = 0.0
    if model_family == "seq2seq":
        processor._synchronize()
        encoder_started = time.perf_counter()
        with torch.no_grad():
            encoder_outputs = model.get_encoder()(**encoded, return_dict=True)
        processor._synchronize()
        lm_seconds += time.perf_counter() - encoder_started
        next_input = tokenizer(task.prompt, return_tensors="pt")["input_ids"].to(
            device
        )
        if not next_input.shape[-1]:
            next_input = torch.tensor(
                [[decoder_start_token_id(model, tokenizer)]], device=device
            )
        decoder_context_ids = next_input[0].tolist()
    else:
        next_input = inputs

    generated_ids: list[int] = []
    rejected: list[dict] = []
    support_expansions = 0
    parser_fail_closed = False
    rejected_parser_token_id = None
    java_online_stop_triggered = False
    effective_temperature = 0.0 if args.greedy_first and rank == 0 else args.temperature

    for step in range(args.max_new_tokens):
        processor._synchronize()
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
        processor._synchronize()
        lm_seconds += time.perf_counter() - lm_started
        past = outputs.past_key_values
        logits = outputs.logits[:, -1, :].float()
        mask_prefix = torch.tensor(
            [decoder_context_ids + generated_ids], device=device
        )
        try:
            masked_logits = processor(mask_prefix, logits.clone())
        except SynCodeParserFailure:
            parser_fail_closed = True
            if generated_ids:
                rejected_parser_token_id = generated_ids.pop()
            break

        sampling_logits = logits
        if effective_temperature > 0:
            sampling_logits = sampling_logits / effective_temperature
        top_scores, top_ids = torch.topk(
            sampling_logits[0], k=min(args.top_k, sampling_logits.shape[-1])
        )
        base_weights = torch.softmax(top_scores, dim=-1)
        weights = base_weights.clone()
        if effective_temperature > 0 and args.top_p < 1.0:
            remove = torch.cumsum(weights, dim=-1) > args.top_p
            remove[1:] = remove[:-1].clone()
            remove[0] = False
            weights[remove] = 0

        accepted_id = None
        rejected_local_indices: list[int] = []
        rejected_token_ids: set[int] = set()
        expanded_to_full_support = False
        while weights.sum().item() > 0:
            if effective_temperature > 0:
                local_index = int(torch.multinomial(weights, 1).item())
            else:
                local_index = int(torch.argmax(weights).item())
            token_id = int(top_ids[local_index].item())
            if torch.isfinite(masked_logits[0, token_id]):
                accepted_id = token_id
                break
            rejected.append(
                {
                    "step": step,
                    "token_id": token_id,
                    "token": tokenizer.decode(
                        [token_id],
                        skip_special_tokens=False,
                        clean_up_tokenization_spaces=False,
                    ),
                }
            )
            rejected_local_indices.append(local_index)
            rejected_token_ids.add(token_id)
            weights[local_index] = 0
            if weights.sum().item() == 0:
                if (
                    args.expand_sampling_support
                    and not expanded_to_full_support
                    and top_ids.numel() < sampling_logits.shape[-1]
                ):
                    # A constrained mask can reject the entire top-k set even
                    # when a valid token has lower ordinary-model probability.
                    # Expand once to the complete vocabulary before giving up;
                    # this is intentionally expensive and is opt-in so all
                    # frozen rows retain their original sampling contract.
                    top_scores, top_ids = torch.sort(
                        sampling_logits[0], descending=True
                    )
                    base_weights = torch.softmax(top_scores, dim=-1)
                    weights = base_weights.clone()
                    if effective_temperature > 0 and args.top_p < 1.0:
                        remove = torch.cumsum(weights, dim=-1) > args.top_p
                        remove[1:] = remove[:-1].clone()
                        remove[0] = False
                        weights[remove] = 0
                    if rejected_token_ids:
                        rejected_tensor = torch.tensor(
                            sorted(rejected_token_ids), device=device
                        )
                        weights[rejected_tensor] = 0
                    expanded_to_full_support = True
                    support_expansions += 1
                    continue
                weights, expanded = _restore_sampling_support(
                    base_weights, weights, rejected_local_indices
                )
                support_expansions += int(expanded)
        if accepted_id is None or accepted_id == tokenizer.eos_token_id:
            break
        generated_ids.append(accepted_id)
        next_input = torch.tensor([[accepted_id]], device=device)

        if args.java_online_stop and model_family == "seq2seq":
            generated_text = tokenizer.decode(
                decoder_context_ids + generated_ids,
                skip_special_tokens=True,
                clean_up_tokenization_spaces=False,
            )
            generated_source = extract_java_source(generated_text)
            _, policy = finalize_syncode_java_source(
                generated_source, len(task.prompt)
            )
            if policy == "complete_unit_truncation":
                java_online_stop_triggered = True
                break

    generated_suffix = tokenizer.decode(
        generated_ids,
        skip_special_tokens=True,
        clean_up_tokenization_spaces=False,
    )
    generated_text = tokenizer.decode(
        decoder_context_ids + generated_ids,
        skip_special_tokens=True,
        clean_up_tokenization_spaces=False,
    )
    source = materialize_syncode_candidate(task, generated_text, model_family)
    java_postprocess = "disabled"
    if args.java_safe_completion:
        source, java_postprocess = finalize_syncode_java_source(
            source, len(task.prompt)
        )
    processor._synchronize()
    elapsed_seconds = time.perf_counter() - started
    output_tokens = len(generated_ids)
    constraint_seconds = processor.constraint_seconds
    parser_fallback = bool(processor.grammar_engine.parse_failed)
    return source, {
        "method": "syncode_java_cfg_proposal_preserving_rejection",
        "task_id": task.task_id,
        "problem_index": task.index,
        "candidate_rank": rank,
        "seed": seed,
        "model": args.model,
        "tokenizer": args.tokenizer or args.model,
        "model_family": model_family,
        "grammar": args.grammar,
        "syncode_mode": args.syncode_mode,
        "proposal_preserving_rejection": True,
        "temperature": effective_temperature,
        "top_p": args.top_p,
        "top_k": args.top_k,
        "generated_text": generated_text,
        "generated_suffix": generated_suffix,
        "generated_token_ids": generated_ids,
        "rejected_tokens": rejected,
        "constraint_support_expansions": support_expansions,
        "expand_sampling_support": args.expand_sampling_support,
        "parser_fallback_to_unconstrained": parser_fallback,
        "parser_fail_closed": parser_fail_closed,
        "rejected_parser_token_id": rejected_parser_token_id,
        "generation_timed_out": False,
        "source": source,
        "java_safe_completion": args.java_safe_completion,
        "java_postprocess": java_postprocess,
        "java_online_stop": args.java_online_stop,
        "java_online_stop_triggered": java_online_stop_triggered,
        "input_tokens": int(inputs.shape[-1]),
        "decoder_prefix_tokens": len(decoder_context_ids),
        "output_tokens": output_tokens,
        "decoder_steps_observed": processor.constraint_calls,
        "constraint_calls": processor.constraint_calls,
        "constraint_seconds": constraint_seconds,
        "lm_seconds": lm_seconds,
        "non_constraint_seconds": max(0.0, elapsed_seconds - constraint_seconds),
        "constraint_seconds_per_decoder_step": _per_unit(
            constraint_seconds, processor.constraint_calls
        ),
        "constraint_seconds_per_output_token": _per_unit(
            constraint_seconds, output_tokens
        ),
        "elapsed_seconds_per_output_token": _per_unit(
            elapsed_seconds, output_tokens
        ),
        "elapsed_seconds": elapsed_seconds,
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
                "method": (
                    "syncode_java_cfg_proposal_preserving_rejection"
                    if args.proposal_preserving_rejection
                    else "syncode_java_cfg"
                ),
                "dataset_rows": len(all_tasks),
                "selected_rows": len(tasks),
                "grammar": args.grammar,
                "score_dataset": str(score_dataset_path),
            }
        )
        return target

    run_started = time.perf_counter()
    initialization_started = time.perf_counter()
    torch, tokenizer, model, device, processor, model_family = load_runtime(args)
    initialization_seconds = time.perf_counter() - initialization_started
    writer = CandidateWriter(target, resume=args.resume)
    candidate_ranks = select_candidate_ranks(args.candidates, args.candidate_ranks)
    candidate_execution_started = time.perf_counter()
    for task in tasks:
        inputs, decoder_prefix_tokens = tokenize_prompt(
            tokenizer, task, device, model_family
        )
        prompt_length = int(inputs["input_ids"].shape[-1])
        for rank in candidate_ranks:
            if args.resume and not writer.pending(task.index, rank):
                continue
            seed = args.seed + task.index * args.candidates + rank
            torch.manual_seed(seed)
            processor.reset()
            parser_prefix = task.prompt
            nested_generic_rewrites = 0
            if not args.disable_java_nested_generic_prefix_normalization:
                parser_prefix, nested_generic_rewrites = (
                    normalize_java_nested_generic_prefix(task.prompt)
                )
            processor.set_fixed_parser_prefix(task.prompt, parser_prefix)
            if args.proposal_preserving_rejection:
                try:
                    with candidate_time_limit(args.candidate_timeout_seconds):
                        source, trajectory = generate_proposal_preserving_candidate(
                            args,
                            task,
                            rank,
                            torch,
                            tokenizer,
                            model,
                            device,
                            processor,
                            model_family,
                        )
                except CandidateGenerationTimeout as exc:
                    processor._synchronize()
                    trajectory = {
                        "method": "syncode_java_cfg_proposal_preserving_rejection",
                        "task_id": task.task_id,
                        "problem_index": task.index,
                        "candidate_rank": rank,
                        "seed": seed,
                        "model": args.model,
                        "tokenizer": args.tokenizer or args.model,
                        "model_family": model_family,
                        "grammar": args.grammar,
                        "syncode_mode": args.syncode_mode,
                        "proposal_preserving_rejection": True,
                        "parser_fallback_to_unconstrained": False,
                        "parser_fail_closed": False,
                        "generation_timed_out": True,
                        "timeout_diagnostics": str(exc),
                        "source": task.prompt,
                        "input_tokens": prompt_length,
                        "decoder_prefix_tokens": decoder_prefix_tokens,
                        "output_tokens": None,
                        "decoder_steps_observed": processor.constraint_calls,
                        "constraint_calls": processor.constraint_calls,
                        "constraint_seconds": processor.constraint_seconds,
                        "elapsed_seconds": args.candidate_timeout_seconds,
                    }
                    source = task.prompt
                trajectory.update(
                    nested_generic_prefix_rewrites=nested_generic_rewrites,
                    java_sound_overapprox=args.java_sound_overapprox,
                    generic_closer_splits=(
                        processor.incremental_decoder.generic_closer_splits
                        if processor.incremental_decoder is not None
                        else 0
                    ),
                    cast_elisions=(
                        processor.incremental_decoder.cast_elisions
                        if processor.incremental_decoder is not None
                        else 0
                    ),
                )
                writer.write(task.index, rank, source, trajectory)
                continue
            processor._synchronize()
            started = time.perf_counter()
            effective_temperature = (
                0.0 if args.greedy_first and rank == 0 else args.temperature
            )
            generation_kwargs = {
                "max_new_tokens": args.max_new_tokens,
                "do_sample": effective_temperature > 0,
                "pad_token_id": (
                    tokenizer.pad_token_id
                    if tokenizer.pad_token_id is not None
                    else tokenizer.eos_token_id
                ),
                "eos_token_id": tokenizer.eos_token_id,
                "logits_processor": [processor],
            }
            java_stopping = None
            if args.java_online_stop and model_family == "seq2seq":
                java_stopping = JavaCompilationUnitStoppingCriteria(
                    tokenizer, len(task.prompt)
                )
                generation_kwargs["stopping_criteria"] = [java_stopping]
            if effective_temperature > 0:
                generation_kwargs.update(
                    temperature=effective_temperature,
                    top_p=args.top_p,
                    top_k=args.top_k,
                )
            try:
                with candidate_time_limit(args.candidate_timeout_seconds):
                    generated = model.generate(**inputs, **generation_kwargs)
            except SynCodeParserFailure as exc:
                processor._synchronize()
                elapsed_seconds = time.perf_counter() - started
                constraint_seconds = processor.constraint_seconds
                accepted_ids = exc.input_ids[0, :-1]
                completion_ids = (
                    accepted_ids
                    if model_family == "seq2seq"
                    else accepted_ids[prompt_length:]
                )
                raw = tokenizer.decode(completion_ids, skip_special_tokens=True)
                source = materialize_syncode_candidate(task, raw, model_family)
                java_postprocess = "disabled"
                if args.java_safe_completion:
                    source, java_postprocess = finalize_syncode_java_source(
                        source, len(task.prompt)
                    )
                output_tokens = max(
                    0, int(completion_ids.shape[-1]) - decoder_prefix_tokens
                )
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
                        "tokenizer": args.tokenizer or args.model,
                        "model_family": model_family,
                        "grammar": args.grammar,
                        "syncode_mode": args.syncode_mode,
                        "temperature": effective_temperature,
                        "parser_fallback_to_unconstrained": False,
                        "parser_fail_closed": True,
                        "rejected_parser_token_id": int(exc.input_ids[0, -1]),
                        "generation_timed_out": False,
                        "raw_response": raw,
                        "source": source,
                        "java_safe_completion": args.java_safe_completion,
                        "java_postprocess": java_postprocess,
                        "java_online_stop": args.java_online_stop,
                        "java_online_stop_triggered": False,
                        "input_tokens": prompt_length,
                        "decoder_prefix_tokens": decoder_prefix_tokens,
                        "output_tokens": output_tokens,
                        "decoder_steps_observed": processor.constraint_calls,
                        "constraint_calls": processor.constraint_calls,
                        "constraint_seconds": constraint_seconds,
                        "non_constraint_seconds": max(
                            0.0, elapsed_seconds - constraint_seconds
                        ),
                        "constraint_seconds_per_decoder_step": _per_unit(
                            constraint_seconds, processor.constraint_calls
                        ),
                        "constraint_seconds_per_output_token": _per_unit(
                            constraint_seconds, output_tokens
                        ),
                        "elapsed_seconds_per_output_token": _per_unit(
                            elapsed_seconds, output_tokens
                        ),
                        "incremental_input_decode": (
                            processor.incremental_decoder is not None
                        ),
                        "java_sound_overapprox": args.java_sound_overapprox,
                        "generic_closer_splits": (
                            processor.incremental_decoder.generic_closer_splits
                            if processor.incremental_decoder is not None
                            else 0
                        ),
                        "cast_elisions": (
                            processor.incremental_decoder.cast_elisions
                            if processor.incremental_decoder is not None
                            else 0
                        ),
                        "elapsed_seconds": elapsed_seconds,
                    },
                )
                continue
            except CandidateGenerationTimeout as exc:
                processor._synchronize()
                elapsed_seconds = time.perf_counter() - started
                constraint_seconds = processor.constraint_seconds
                writer.write(
                    task.index,
                    rank,
                    task.prompt,
                    {
                        "method": "syncode_java_cfg",
                        "task_id": task.task_id,
                        "problem_index": task.index,
                        "candidate_rank": rank,
                        "seed": seed,
                        "model": args.model,
                        "tokenizer": args.tokenizer or args.model,
                        "model_family": model_family,
                        "grammar": args.grammar,
                        "syncode_mode": args.syncode_mode,
                        "temperature": effective_temperature,
                        "parser_fallback_to_unconstrained": bool(
                            processor.grammar_engine.parse_failed
                        ),
                        "generation_timed_out": True,
                        "timeout_diagnostics": str(exc),
                        "source": task.prompt,
                        "input_tokens": prompt_length,
                        "decoder_prefix_tokens": decoder_prefix_tokens,
                        "output_tokens": None,
                        "decoder_steps_observed": processor.constraint_calls,
                        "constraint_calls": processor.constraint_calls,
                        "constraint_seconds": constraint_seconds,
                        "non_constraint_seconds": max(
                            0.0, elapsed_seconds - constraint_seconds
                        ),
                        "constraint_seconds_per_decoder_step": _per_unit(
                            constraint_seconds, processor.constraint_calls
                        ),
                        "elapsed_seconds": elapsed_seconds,
                        "incremental_input_decode": (
                            processor.incremental_decoder is not None
                        ),
                        "nested_generic_prefix_rewrites": nested_generic_rewrites,
                        "parser_prefix_rewrite_applied_calls": (
                            processor.incremental_decoder.prefix_rewrite_applied_calls
                            if processor.incremental_decoder is not None
                            else 0
                        ),
                        "java_sound_overapprox": args.java_sound_overapprox,
                        "generic_closer_splits": (
                            processor.incremental_decoder.generic_closer_splits
                            if processor.incremental_decoder is not None
                            else 0
                        ),
                        "cast_elisions": (
                            processor.incremental_decoder.cast_elisions
                            if processor.incremental_decoder is not None
                            else 0
                        ),
                    },
                )
                continue
            parser_fallback = bool(processor.grammar_engine.parse_failed)
            completion_ids = (
                generated[0]
                if model_family == "seq2seq"
                else generated[0, prompt_length:]
            )
            raw = tokenizer.decode(completion_ids, skip_special_tokens=True)
            source = materialize_syncode_candidate(task, raw, model_family)
            java_postprocess = "disabled"
            if args.java_safe_completion:
                source, java_postprocess = finalize_syncode_java_source(
                    source, len(task.prompt)
                )
            output_tokens = (
                int(completion_ids.shape[-1]) - decoder_prefix_tokens
            )
            processor._synchronize()
            elapsed_seconds = time.perf_counter() - started
            constraint_seconds = processor.constraint_seconds
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
                    "tokenizer": args.tokenizer or args.model,
                    "model_family": model_family,
                    "grammar": args.grammar,
                    "syncode_mode": args.syncode_mode,
                    "parser_fallback_to_unconstrained": parser_fallback,
                    "parser_fail_closed": False,
                    "generation_timed_out": False,
                    "temperature": effective_temperature,
                    "lm_prompt_mode": "raw_prefix",
                    "decoder_prefix_mode": (
                        "forced_benchmark_prefix"
                        if model_family == "seq2seq"
                        else "causal_context"
                    ),
                    "raw_response": raw,
                    "source": source,
                    "java_safe_completion": args.java_safe_completion,
                    "java_postprocess": java_postprocess,
                    "java_online_stop": args.java_online_stop,
                    "java_online_stop_triggered": bool(
                        java_stopping is not None and java_stopping.triggered
                    ),
                    "input_tokens": prompt_length,
                    "decoder_prefix_tokens": decoder_prefix_tokens,
                    "output_tokens": output_tokens,
                    "decoder_steps_observed": processor.constraint_calls,
                    "constraint_calls": processor.constraint_calls,
                    "constraint_seconds": constraint_seconds,
                    "non_constraint_seconds": max(
                        0.0, elapsed_seconds - constraint_seconds
                    ),
                    "constraint_seconds_per_decoder_step": _per_unit(
                        constraint_seconds, processor.constraint_calls
                    ),
                    "constraint_seconds_per_output_token": _per_unit(
                        constraint_seconds, output_tokens
                    ),
                    "elapsed_seconds_per_output_token": _per_unit(
                        elapsed_seconds, output_tokens
                    ),
                    "incremental_input_decode": (
                        processor.incremental_decoder is not None
                    ),
                    "incremental_decode_cache_hits": (
                        processor.incremental_decoder.cache_hits
                        if processor.incremental_decoder is not None
                        else None
                    ),
                    "nested_generic_prefix_rewrites": nested_generic_rewrites,
                    "parser_prefix_rewrite_applied_calls": (
                        processor.incremental_decoder.prefix_rewrite_applied_calls
                        if processor.incremental_decoder is not None
                        else 0
                    ),
                    "java_sound_overapprox": args.java_sound_overapprox,
                    "generic_closer_splits": (
                        processor.incremental_decoder.generic_closer_splits
                        if processor.incremental_decoder is not None
                        else 0
                    ),
                    "cast_elisions": (
                        processor.incremental_decoder.cast_elisions
                        if processor.incremental_decoder is not None
                        else 0
                    ),
                    "elapsed_seconds": elapsed_seconds,
                },
            )
    candidate_execution_seconds = time.perf_counter() - candidate_execution_started
    run_wall_seconds = time.perf_counter() - run_started
    writer.write_manifest(
        common_manifest(
            method=(
                "syncode_java_cfg_proposal_preserving_rejection"
                if args.proposal_preserving_rejection
                else "syncode_java_cfg"
            ),
            dataset_path=dataset_path,
            score_dataset_path=score_dataset_path,
            args=vars(args),
        )
        | {
            "model": args.model,
            "tokenizer": args.tokenizer or args.model,
            "model_family": model_family,
            "constraint_scope": "Java context-free syntax only; no type guarantee",
            "java_parser_prefix_compatibility": (
                "split consecutive generic-closing > characters only in the fixed "
                "benchmark-prefix parser view; model input and emitted Java are unchanged"
            ),
            "parse_failure_policy": (
                "fail closed at the last accepted prefix"
                if args.fail_closed_on_parse_error
                else "record upstream SynCode fallback to unconstrained decoding"
            ),
            "proposal_preserving_rejection": args.proposal_preserving_rejection,
            "proposal_preserving_rejection_scope": (
                "sample from the matched ordinary top-k/top-p distribution first; "
                "retain a legal proposal unchanged and resample only after the "
                "SynCode grammar mask rejects it"
                if args.proposal_preserving_rejection
                else None
            ),
            "java_sound_overapprox": args.java_sound_overapprox,
            "ignored_whitespace_token_mask_repair": {
                "token_count": processor.ignored_whitespace_token_repairs,
                "scope": (
                    "pure-whitespace tokenizer pieces only when the parse result "
                    "explicitly permits ignored WS"
                ),
            },
            "java_sound_overapprox_scope": (
                "parser-view-only nested-generic closer splitting and completed-cast "
                "elision; cast grammar alternative disabled; model input/output unchanged"
                if args.java_sound_overapprox
                else None
            ),
            "java_safe_completion": args.java_safe_completion,
            "java_safe_completion_scope": (
                "truncate after first complete compilation-unit brace; if no class "
                "close exists, close the class only after the target method closed"
                if args.java_safe_completion
                else None
            ),
            "java_online_stop": args.java_online_stop,
            "timing_protocol": (
                "constraint_seconds measures SyncodeLogitsProcessor wall time; "
                "non_constraint_seconds is total generation minus constraint time"
            ),
            "runtime_timing": {
                "initialization_seconds": initialization_seconds,
                "candidate_execution_seconds": candidate_execution_seconds,
                "run_wall_seconds_before_manifest_write": run_wall_seconds,
            },
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
    parser.add_argument("--tokenizer", default="")
    parser.add_argument("--model_family", choices=["auto", "causal", "seq2seq"], default="auto")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--dtype", choices=["auto", "bf16", "fp16", "fp32"], default="bf16")
    parser.add_argument("--local_files_only", action="store_true")
    parser.add_argument("--grammar", default="java")
    parser.add_argument(
        "--java_sound_overapprox",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Use the MBJP-audited conservative Java parser view that avoids known "
            "false pruning for nested generics and reference casts."
        ),
    )
    parser.add_argument(
        "--java_safe_completion",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Apply the Java equivalent of SynCode's evaluation-time backup "
            "completion without changing the generated method body."
        ),
    )
    parser.add_argument(
        "--java_online_stop",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Stop immediately once the generated benchmark Java class closes.",
    )
    parser.add_argument("--syncode_mode", choices=["grammar_mask", "grammar_strict"], default="grammar_mask")
    parser.add_argument("--parser", choices=["lr", "lalr"], default="lalr")
    parser.add_argument("--rebuild_mask_store", action="store_true")
    parser.add_argument(
        "--disable_incremental_input_decode",
        action="store_true",
        help=(
            "Use upstream full-prefix token-id decoding on every step. The default "
            "incremental decoder is mask-equivalent and reduces Python/copy overhead."
        ),
    )
    parser.add_argument(
        "--disable_java_nested_generic_prefix_normalization",
        action="store_true",
        help=(
            "Disable parser-view-only spacing of nested generic closers in the fixed "
            "Java benchmark prefix."
        ),
    )
    parser.add_argument("--dev_mode", action="store_true")
    parser.add_argument(
        "--fail_closed_on_parse_error",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Stop at the last accepted prefix when grammar-mask overapproximation "
            "admits a token that the incremental parser then rejects."
        ),
    )
    parser.add_argument("--candidates", type=int, default=10)
    parser.add_argument(
        "--candidate_ranks",
        default="",
        help="Optional comma-separated rank shard; seeds retain the full candidate count.",
    )
    parser.add_argument("--max_new_tokens", type=int, default=1024)
    parser.add_argument("--max_input_tokens", type=int, default=1024)
    parser.add_argument(
        "--proposal_preserving_rejection",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Preserve matched ordinary proposals and resample only after a SynCode "
            "rejection; disable to reproduce upstream pre-sampling logit masking."
        ),
    )
    parser.add_argument(
        "--expand_sampling_support",
        action=argparse.BooleanOptionalAction,
        default=False,
        help=(
            "When SynCode rejects the complete top-k support, resample once from "
            "the full vocabulary. This maximizes feasible-token recall at extra "
            "GPU/checker cost and is disabled for frozen rows."
        ),
    )
    parser.add_argument(
        "--candidate_timeout_seconds",
        type=float,
        default=0.0,
        help="Fail one candidate closed after this wall-clock budget; 0 disables it.",
    )
    parser.add_argument("--temperature", type=float, default=0.8)
    parser.add_argument(
        "--greedy_first",
        action="store_true",
        help="Use greedy decoding for rank 0 and sampling for later candidates.",
    )
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
