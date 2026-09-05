"""Run a test-free decoder-only baseline on the SuFu benchmark.

This is deliberately a generic prompting wrapper.  It does not expose the
SuFu tests or expected interpreter output to the model and does not add a
grammar/type checker during generation.  The existing ``score_sufu_no_write``
script remains the only functional scorer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pickle
import re
import sys
import time
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from baselines.java_baselines.common import (  # noqa: E402
    CandidateWriter,
    common_manifest,
    load_json_rows,
    output_directory,
    select_tasks,
    sha256_file,
)
from baselines.java_baselines.model_clients import (  # noqa: E402
    add_model_client_arguments,
    build_client,
)


SYSTEM = (
    "You generate SuFu programs. Return only one complete SuFu source program, "
    "without Markdown fences, tests, interpreter output, or explanation."
)

SYSTEM_HIGH_INFORMATION = (
    "You are solving a SuFu synthesis task. The target task description and its "
    "public type/helper prefix are authoritative. Use them to construct a "
    "complete, executable SuFu source program, preserving the declared "
    "constructors and helper interfaces. Return only that source program: do "
    "not emit tests, interpreter outputs, hidden examples, Markdown fences, or "
    "analysis. The demonstrations are unrelated training examples; adapt their "
    "recursive, Compress, align/label/unlabel, and data-structure patterns to "
    "the target rather than copying their task semantics."
)

# A generic Full-Output condition: the benchmark scorer compares the complete
# interpreter transcript, including declaration signatures.  This profile
# makes that output contract explicit without revealing tests or expected
# values, and is intentionally model-agnostic.
SYSTEM_FULL_OUTPUT = (
    "You are solving a SuFu synthesis task for a full-source evaluator. The "
    "target task description and its public type/helper prefix are authoritative. "
    "Return one complete executable SuFu source program, including every "
    "declaration needed before main. If the task semantics require a hidden "
    "target or representation transformation, infer and emit that target/"
    "representation definition as well; do not omit it and do not replace it "
    "with a shortcut. Preserve the declared constructors and helper interfaces. "
    "Return only source: no tests, interpreter output, Markdown fences, or "
    "explanation. Demonstrations are unrelated training examples; adapt their "
    "source patterns rather than copying task semantics."
)


def _source_prefix(prompt: str) -> str:
    """Remove the natural-language header from an original SuFu prefix."""
    match = re.search(r"(?m)^\s*Inductive\b", prompt)
    return prompt[match.start() :].strip() if match else prompt.strip()


def _clean_response(text: str) -> str:
    text = str(text).strip()
    fenced = re.findall(r"```(?:sufu|ml|ocaml)?\s*(.*?)```", text, flags=re.I | re.S)
    if fenced:
        text = max(fenced, key=len).strip()

    # Full-source few-shot prompts contain explicit ``TASK DESCRIPTION/PREFIX``
    # and ``TARGET SUFU TASK`` delimiters.  A causal model can copy those
    # demonstrations into its completion.  Do not pass copied demonstrations
    # to the scorer as if they were the target program: when code follows the
    # last target marker, keep that code; otherwise keep the generated prefix
    # before the first copied example block.  This also handles models that
    # start a target definition and only then reproduce the prompt.
    example_marker = re.search(r"(?m)^\s*TASK DESCRIPTION/PREFIX:\s*", text)
    target_markers = list(re.finditer(r"(?m)^\s*TARGET SUFU TASK:\s*", text))
    if target_markers:
        tail = text[target_markers[-1].end() :].strip()
        # A real SuFu program normally contains a declaration/definition and
        # at least one semicolon.  Keep a substantive tail when the model
        # copied the full prompt and generated after its target marker.
        if ";" in tail and re.search(r"\b(?:Inductive|main\s*=|fix\s*\(|=)\b", tail):
            text = tail
        elif example_marker and ";" in text[: example_marker.start()]:
            text = text[: example_marker.start()].rstrip()
    elif example_marker and ";" in text[: example_marker.start()]:
        text = text[: example_marker.start()].rstrip()

    # In prefix mode a base code model may continue the demonstration stream
    # after producing a target ``main``.  The target prefix is already
    # materialized separately, so a later top-level ``Inductive`` declaration
    # is prompt-copy contamination, not part of the candidate.  Keep the
    # first complete program while preserving legitimate multiple inductive
    # declarations that occur before ``main`` in full-source mode.
    inductives = list(re.finditer(r"(?m)^\s*Inductive\b", text))
    main_match = re.search(r"(?m)^\s*main\s*=", text)
    main_pos = main_match.start() if main_match else -1
    if inductives and main_pos >= 0:
        # If the first inductive declaration follows ``main`` there was no
        # source prefix in the completion; it is likewise a restarted demo.
        start = 0 if inductives[0].start() > main_pos else 1
        later = [m.start() for m in inductives[start:] if m.start() > main_pos]
        if later and ";" in text[: later[0]]:
            text = text[: later[0]].rstrip()

    match = re.search(r"(?m)^\s*Inductive\b", text)
    if match:
        text = text[match.start() :]
    # Chat-tuned causal models can continue by copying the next role/prompt
    # after an otherwise complete SuFu program.  Keep only the generated
    # program when a transcript marker follows it.  This is deliberately
    # conservative: a marker is removed only if a program terminator (`;`)
    # already occurs before it.
    transcript_markers = ("\nuser\n", "\nassistant\n", "\nTARGET SUFU TASK:", "\n<|im_start|>")
    cut_positions = [
        position
        for marker in transcript_markers
        if (position := text.find(marker)) >= 0 and ";" in text[:position]
    ]
    if cut_positions:
        text = text[: min(cut_positions)]

    # Some base models emit a complete SuFu ``main`` definition and then
    # continue with an English explanation.  In the benchmark grammar the
    # first semicolon after a top-level ``main =`` is the declaration
    # terminator, so discard trailing prose after that point.  This is a
    # presentation/interface cleanup only; it does not alter the generated
    # SuFu source before ``main`` or add any model-specific repair.
    main_match = re.search(r"(?m)^\s*main\s*=", text)
    if main_match:
        main_terminator = text.find(";", main_match.end())
        if main_terminator >= 0 and text[main_terminator + 1 :].strip():
            text = text[: main_terminator + 1]
    return text.strip()


def materialize_source(row: dict, response: str, prompt_mode: str) -> str:
    generated = _clean_response(response)
    if prompt_mode == "prefix":
        # Original SuFu rows expose a source prefix ending before the target
        # definition.  The scorer expects a complete program, so concatenate
        # only the source part of that prefix with the model continuation.
        if re.search(r"(?m)^\s*Inductive\b", generated):
            return generated
        return (_source_prefix(str(row["prompt"])) + "\n" + generated).strip()
    if prompt_mode != "full_source":
        raise ValueError(f"unsupported prompt mode: {prompt_mode}")
    return generated


def _example_block(row: dict, prompt_mode: str) -> str:
    prompt = str(row.get("prompt", "")).strip()
    code = str(row.get("code", "")).strip()
    if prompt_mode == "prefix":
        prompt = _source_prefix(prompt)
    # Keep the demonstration delimiter distinct from the target completion
    # delimiter.  Some causal base models (notably SmolLM3) learn that
    # ``COMPLETE SUFU SOURCE:`` is the end-of-turn boundary and emit EOS when
    # the same marker appears repeatedly in a few-shot prompt.  The target
    # marker remains ``COMPLETE SUFU SOURCE:`` so the model has exactly one
    # unambiguous place to begin the requested source program.
    return f"TASK DESCRIPTION/PREFIX:\n{prompt}\nEXAMPLE SUFU SOURCE:\n{code}"


def build_messages(
    row: dict,
    examples: list[dict],
    prompt_mode: str,
    guidance_profile: str = "default",
) -> list[dict[str, str]]:
    if prompt_mode == "prefix":
        # Keep Base-model completion genuinely code-continuation shaped: no
        # natural-language header is inserted between the source prefix and
        # the unknown suffix.  Demonstrations, when requested, are complete
        # source streams and contain no tests or interpreter output.  The
        # demonstration ``code`` field is already a complete source program;
        # appending its prompt prefix a second time would duplicate type and
        # function declarations and teach the model an invalid format.
        streams = []
        for example in examples:
            streams.append(str(example.get("code", "")).strip())
        streams.append(_source_prefix(str(row.get("prompt", ""))))
        return [{"role": "user", "content": "\n\n".join(streams)}]
    blocks = []
    if examples:
        blocks.append(
            "The following are fixed training examples. Do not copy their tests "
            "or outputs; solve the new task using the same source format."
        )
        blocks.extend(_example_block(example, prompt_mode) for example in examples)
    prompt = str(row.get("prompt", "")).strip()
    blocks.append("TARGET SUFU TASK:\n" + prompt)
    if guidance_profile in {"high_information", "full_output"}:
        blocks.append(
            "Now solve the target above. Include every declaration needed by the "
            "target prefix and finish with one complete `main` definition. "
            "Follow the target's exact task semantics; the scorer will execute "
            "the public test cases separately."
        )
    elif guidance_profile != "default":
        raise ValueError(f"unsupported guidance profile: {guidance_profile}")
    # Make the completion boundary explicit for base models.  Demonstration
    # blocks use the same label; omitting it on the target causes non-chat
    # models to continue by copying another TASK DESCRIPTION/PREFIX block or
    # to emit a file-separator token instead of starting the requested source.
    blocks.append("COMPLETE SUFU SOURCE:")
    if guidance_profile == "full_output":
        system = SYSTEM_FULL_OUTPUT
    elif guidance_profile == "high_information":
        system = SYSTEM_HIGH_INFORMATION
    else:
        system = SYSTEM
    return [{"role": "system", "content": system}, {"role": "user", "content": "\n\n".join(blocks)}]


def _row_id(row: dict) -> str:
    return str(row.get("task_id", row.get("file_name", "")))


def _validate_few_shot_rows(rows: list[dict]) -> None:
    """Reject explicit test/validation/debug-overlap demonstrations."""
    unsafe = [
        _row_id(row)
        for row in rows
        if row.get("debug_overlap")
        or row.get("type") in {"debug", "test", "valid"}
        or row.get("original_split") in {"test", "valid"}
        or row.get("split") in {"test", "valid"}
    ]
    if unsafe:
        raise ValueError(
            "few-shot examples must not come from test/valid/debug rows: "
            + ", ".join(unsafe)
        )


def _align_rows(rows: list[dict], score_path: Path) -> list[dict]:
    score_rows = pickle.loads(score_path.read_bytes())
    if len(rows) != len(score_rows):
        raise RuntimeError(f"generation/scoring row count mismatch: {len(rows)} != {len(score_rows)}")
    expected = [str(row.get("file_name", row.get("task_id", ""))) for row in score_rows]
    by_id = {_row_id(row): row for row in rows}
    if len(by_id) != len(rows) or any(identifier not in by_id for identifier in expected):
        raise RuntimeError("could not align SuFu prompts to the frozen scorer rows")
    return [by_id[identifier] for identifier in expected]


def _fingerprint(rows: list[dict]) -> str:
    digest = hashlib.sha256()
    for row in rows:
        digest.update(_row_id(row).encode())
        digest.update(str(row.get("prompt", "")).encode())
        digest.update(str(row.get("code", "")).encode())
    return digest.hexdigest()


def run(args: argparse.Namespace) -> Path:
    dataset_path = Path(args.dataset_json)
    rows = load_json_rows(dataset_path)
    score_path = Path("Utils/data") / args.score_task / f"{args.score_split}.pkl"
    if not score_path.is_file():
        raise FileNotFoundError(score_path)
    rows = _align_rows(rows, score_path)
    selected = select_tasks(rows, args.indices, args.limit)
    examples = []
    if args.few_shot_k:
        available_examples = load_json_rows(Path(args.few_shot_dataset))
        if args.few_shot_ids:
            wanted = [item.strip() for item in args.few_shot_ids.split(",") if item.strip()]
            by_id = {_row_id(row): row for row in available_examples}
            missing = [item for item in wanted if item not in by_id]
            if missing:
                raise ValueError(f"few-shot example ids not found: {missing}")
            examples = [by_id[item] for item in wanted[: args.few_shot_k]]
        else:
            examples = available_examples[: args.few_shot_k]
        if len(examples) != args.few_shot_k:
            raise ValueError("few-shot dataset has fewer rows than few_shot_k")
        _validate_few_shot_rows(examples)
        # Examples are training rows only; tests and expected outputs are never
        # inserted into messages, even if they are present in the JSON object.
        examples = [
            {"task_id": _row_id(row), "prompt": row.get("prompt", ""), "code": row.get("code", "")}
            for row in examples
        ]
    target = output_directory(args.score_task, args.score_split, args.output_tag)
    if args.dry_run:
        print(
            {
                "method": "hf_sufu_decoder_only",
                "model": args.model,
                "dataset_rows": len(rows),
                "selected_rows": len(selected),
                "few_shot_k": args.few_shot_k,
                "prompt_mode": args.prompt_mode,
                "hidden_tests_exposed": False,
            }
        )
        return target

    client = build_client(args)
    writer = CandidateWriter(target, resume=args.resume)
    for index, row in enumerate(selected):
        # ``select_tasks`` preserves the frozen scorer index only when no
        # subset is selected; explicit subsets retain their original position
        # through this lookup.
        problem = rows.index(row)
        messages = build_messages(row, examples, args.prompt_mode, args.guidance_profile)
        for rank in range(args.candidates):
            if args.resume and not writer.pending(problem, rank):
                continue
            started = time.perf_counter()
            seed = args.seed + problem * args.candidates + rank
            temperature = 0.0 if args.greedy_first and rank == 0 else args.temperature
            generated = client.generate(
                messages,
                max_tokens=args.max_tokens,
                temperature=temperature,
                top_p=args.top_p,
                seed=seed,
                stop_strings=[
                    "\nuser\n",
                    "\nassistant\n",
                    "\nTARGET SUFU TASK:",
                    "\n<|im_start|>",
                ],
            )
            source = materialize_source(row, generated.text, args.prompt_mode)
            elapsed = time.perf_counter() - started
            writer.write(
                problem,
                rank,
                source,
                {
                    "method": "hf_sufu_decoder_only",
                    "task_id": _row_id(row),
                    "problem_index": problem,
                    "candidate_rank": rank,
                    "model": client.model_name,
                    "few_shot_k": args.few_shot_k,
                    "prompt_mode": args.prompt_mode,
                    "few_shot_example_ids": [_row_id(example) for example in examples],
                    "hidden_tests_exposed": False,
                    "input_tokens": generated.input_tokens,
                    "output_tokens": generated.output_tokens,
                    "raw_response": generated.text,
                    "elapsed_seconds": elapsed,
                    "lm_seconds": elapsed,
                },
            )

    writer.write_manifest(
        common_manifest(
            method="hf_sufu_decoder_only",
            dataset_path=dataset_path,
            score_dataset_path=score_path,
            args={
                key: value
                for key, value in vars(args).items()
                if key not in {"api_key"}
            }
            | {
                "few_shot_example_ids": [_row_id(example) for example in examples],
                "few_shot_examples_sha256": _fingerprint(examples),
                "hidden_tests_exposed": False,
            },
        )
    )
    print(f"saved candidates to {target}")
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a test-free decoder-only SuFu baseline.")
    parser.add_argument("--dataset_json", required=True)
    parser.add_argument("--score_task", required=True)
    parser.add_argument("--score_split", choices=["train", "valid", "test"], default="test")
    parser.add_argument("--output_tag", required=True)
    parser.add_argument("--few_shot_dataset", default="t5_llm/data/sufu_original_synthetic_half_train_t5.json")
    parser.add_argument("--few_shot_k", type=int, default=0)
    parser.add_argument(
        "--few_shot_ids",
        default="",
        help="comma-separated example task_ids; selects from few_shot_dataset without duplicating data",
    )
    parser.add_argument("--prompt_mode", choices=["prefix", "full_source"], required=True)
    parser.add_argument(
        "--guidance_profile",
        choices=["default", "high_information", "full_output"],
        default="default",
        help="SuFu task instruction profile; high_information is the capability-oriented setting",
    )
    parser.add_argument("--candidates", type=int, default=10)
    parser.add_argument("--max_tokens", type=int, default=1024)
    parser.add_argument("--temperature", type=float, default=0.8)
    parser.add_argument("--greedy_first", action="store_true")
    parser.add_argument("--top_p", type=float, default=0.95)
    parser.add_argument("--seed", type=int, default=273567)
    parser.add_argument("--indices", default="")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry_run", action="store_true")
    add_model_client_arguments(parser)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
