"""Run a test-free zero/few-shot decoder-only Java baseline.

This runner deliberately performs inference only: few-shot examples are
serialized into the prompt and no model parameters are updated.  It shares
the frozen Java scorer and candidate layout with the other baseline runners.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from baselines.java_baselines.common import (
    CandidateWriter,
    align_tasks_to_score,
    common_manifest,
    compile_java_source,
    dataclass_dict,
    extract_java_source,
    load_java_tasks,
    output_directory,
    select_tasks,
    sha256_file,
)
from baselines.java_baselines.model_clients import add_model_client_arguments, build_client


SYSTEM = (
    "You generate Java source code. Return only one complete Java source file, "
    "without Markdown fences or explanation."
)

_IO_EXAMPLE_RE = re.compile(r"^\s*\*\s*>")


def contains_io_examples(text: str) -> bool:
    """Return whether a JavaDoc contains benchmark input/output examples."""
    return any(_IO_EXAMPLE_RE.match(line) for line in text.splitlines())


def _few_shot_block(examples) -> str:
    if not examples:
        return ""
    rendered = [
        "Here are fixed training examples. Follow their Java source format, but solve the new task yourself."
    ]
    for number, example in enumerate(examples, 1):
        rendered.extend(
            [
                f"\nEXAMPLE {number} TASK:\n{example.prompt}",
                f"EXAMPLE {number} COMPLETE SOURCE:\n{example.raw.get('code', '')}",
            ]
        )
    return "\n".join(rendered) + "\n"


def _minimal_format_example(number: int) -> str:
    """Return a semantics-free Java format demonstration."""
    return (
        f"class Example{number} {{\n"
        "    public static void method() {\n"
        "    }\n"
        "}"
    )


_SYNTHETIC_MINIMAL_TASKS = (
    (
        "synthetic_minimal_1",
        # Keep the same source-prompt shape as the Java benchmarks (imports,
        # JavaDoc task statement, class, and open method body), while using a
        # deliberately generic task that cannot identify a benchmark row.
        "import java.io.*;\n"
        "import java.lang.*;\n"
        "import java.util.*;\n"
        "import java.math.*;\n\n\n"
        "class ExampleIdentity {\n"
        "    /**\n"
        "     * * Write a Java function to solve the following task: Return the input integer unchanged.\n"
        "     *\n"
        "     */\n"
        "    public static int identity(int x) {\n",
        "        return x;\n"
        "    }\n"
        "}\n",
    ),
    (
        "synthetic_minimal_2",
        "import java.io.*;\n"
        "import java.lang.*;\n"
        "import java.util.*;\n"
        "import java.math.*;\n\n\n"
        "class ExampleIncrement {\n"
        "    /**\n"
        "     * * Write a Java function to solve the following task: Return the input integer plus one.\n"
        "     *\n"
        "     */\n"
        "    public static int increment(int x) {\n",
        "        return x + 1;\n"
        "    }\n"
        "}\n",
    ),
    (
        "synthetic_minimal_3",
        "import java.io.*;\n"
        "import java.lang.*;\n"
        "import java.util.*;\n"
        "import java.math.*;\n\n\n"
        "class ExampleIsEmpty {\n"
        "    /**\n"
        "     * * Write a Java function to solve the following task: Check whether a string has length zero.\n"
        "     *\n"
        "     */\n"
        "    public static boolean isEmpty(String s) {\n",
        "        return s.length() == 0;\n"
        "    }\n"
        "}\n",
    ),
)


def _synthetic_minimal_examples(count: int) -> list[tuple[str, str, str]]:
    """Return benchmark-shaped, complete, dataset-independent examples.

    Each tuple is ``(task_id, prompt_prefix, body_suffix)``.  The prefix ends
    at the opening method brace, just like the Java benchmark prompts; adding
    the suffix yields the complete source file shown as a demonstration.
    """
    if count < 0 or count > len(_SYNTHETIC_MINIMAL_TASKS):
        raise ValueError(
            "synthetic_minimal supports between 0 and "
            f"{len(_SYNTHETIC_MINIMAL_TASKS)} examples"
        )
    return list(_SYNTHETIC_MINIMAL_TASKS[:count])


def build_messages(
    task,
    examples,
    completion_mode: str,
    *,
    few_shot_style: str = "full",
    minimal_few_shot_k: int = 0,
) -> list[dict[str, str]]:
    if few_shot_style not in {"full", "minimal_format", "synthetic_minimal"}:
        raise ValueError(f"unsupported few-shot style: {few_shot_style}")
    minimal_examples = [
        _minimal_format_example(number) for number in range(1, minimal_few_shot_k + 1)
    ]
    synthetic_examples = (
        _synthetic_minimal_examples(minimal_few_shot_k)
        if few_shot_style == "synthetic_minimal"
        else []
    )
    if completion_mode == "prefix_completion":
        # Base code models are trained on code-continuation streams rather than
        # chat labels.  Concatenate complete demonstration files, then place
        # the target prefix last so generation is a genuine code continuation.
        if few_shot_style == "minimal_format":
            demonstrations = minimal_examples
        elif few_shot_style == "synthetic_minimal":
            demonstrations = [
                prompt.rstrip() + "\n" + suffix.rstrip()
                for _, prompt, suffix in synthetic_examples
            ]
        else:
            demonstrations = [
                example.prompt.rstrip() + "\n" + example.raw.get("code", "").strip()
                for example in examples
            ]
        content = "\n\n".join(demonstrations + [task.prompt.rstrip()])
        return [{"role": "user", "content": content}]
    if few_shot_style == "minimal_format":
        minimal_block = "\n\n".join(
            f"FORMAT EXAMPLE {number}:\n{source}"
            for number, source in enumerate(minimal_examples, 1)
        )
        prompt = (
            "The following are format-only Java skeletons. They contain no task "
            "semantics; use them only to infer source-file formatting.\n\n"
            + minimal_block
            + "\n\nComplete the following Java programming task. Preserve the requested "
            "class and method signature and return the complete source file.\n\n"
            + task.prompt
        )
        return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]
    if few_shot_style == "synthetic_minimal":
        synthetic_block = "\n\n".join(
            f"COMPLETE EXAMPLE {number} TASK:\n{prompt}\n"
            f"COMPLETE EXAMPLE {number} SOURCE:\n{prompt.rstrip()}\n{suffix.rstrip()}"
            for number, (_, prompt, suffix) in enumerate(synthetic_examples, 1)
        )
        prompt = (
            "The following are three independent, complete Java programming "
            "examples. They are synthetic format demonstrations, not benchmark "
            "tasks.\n\n"
            + synthetic_block
            + "\n\nComplete the following Java programming task. Preserve the requested "
            "class and method signature and return the complete source file.\n\n"
            + task.prompt
        )
        return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]
    prompt = (
        _few_shot_block(examples)
        + "Complete the following Java programming task. Preserve the requested "
        "class and method signature and return the complete source file.\n\n"
        + task.prompt
    )
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]


def materialize_source(task, generated_text: str, completion_mode: str) -> str:
    """Turn a decoder completion into the source file scored by the harness.

    Instruction-style causal models often emit a complete file.  Code-completion
    Base models instead continue the Java prefix supplied in ``task.prompt``;
    reconstruct that prefix before applying the common fence/source extraction.
    """
    if completion_mode == "prefix_completion":
        stripped = generated_text.lstrip()
        # Repair prompts can make a Base model emit a short label (for
        # example ``REPAIR:``) immediately before a complete source file.  Do
        # not prepend the benchmark prefix in that case.  Conversely, a
        # normal code continuation may mention a later ``class Main`` after
        # method-body tokens; those must still be appended to the prefix.
        first_source = re.search(
            r"(?m)^\s*(?:import\s+|package\s+|(?:public\s+)?class\s+)",
            generated_text,
        )
        leading = generated_text[: first_source.start()] if first_source else generated_text
        complete_source_prefix = first_source is not None and not re.search(
            r"\b(?:return|if|for|while|switch|try|catch)\b|[;{}]", leading
        )
        if stripped.startswith(("import ", "package ", "public class ", "class ")) or complete_source_prefix:
            # Some Base checkpoints copy the target prefix before emitting a
            # solution.  In that case the completion itself already contains
            # a complete source candidate; avoid duplicating task.prompt.
            text = generated_text
        else:
            text = task.prompt.rstrip() + "\n" + generated_text
        source = extract_java_source(text)
        # StarCoder-style training corpora may append a local driver and then
        # repeat the prompt under a Markdown solution heading.  Neither belongs
        # to the benchmark candidate.
        cut_markers = (
            "\nComplete the following Java programming task.",
            "\n## Solution",
            "\n```",
            "\nclass Main",
            "\npublic class Main",
        )
        cut_positions = [position for marker in cut_markers if (position := source.find(marker)) >= 0]
        # Consecutive imports are legitimate; only treat an import after a
        # closed top-level class as the start of a copied demonstration.
        for match in re.finditer(r"\nimport\s+", source):
            if "}" in source[: match.start()]:
                cut_positions.append(match.start())
                break
        if cut_positions:
            source = source[: min(cut_positions)]
        return source.strip()
    if completion_mode != "full_source":
        raise ValueError(f"unsupported completion mode: {completion_mode}")
    source = extract_java_source(generated_text)
    # A few chat-tuned causal checkpoints (notably MiMo Base) may continue
    # by reproducing the conversation transcript after an otherwise complete
    # Java file (``user``/``assistant`` role labels plus the prompt).  These
    # labels are not Java and must not be handed to javac.  Cut only when a
    # class-closing brace already occurs before the role marker, so a literal
    # word in a comment/string cannot truncate a genuine source file.
    transcript_markers = ("\nuser\n", "\nassistant\n", "\n<|im_start|>")
    cut_positions = [
        position
        for marker in transcript_markers
        if (position := source.find(marker)) >= 0 and "}" in source[:position]
    ]
    if cut_positions:
        source = source[: min(cut_positions)]
    return source.strip()


def _example_fingerprint(examples) -> str:
    digest = hashlib.sha256()
    for example in examples:
        digest.update(str(example.task_id).encode())
        digest.update(example.prompt.encode())
        digest.update(str(example.raw.get("code", "")).encode())
    return digest.hexdigest()


def _minimal_example_fingerprint(count: int) -> str:
    digest = hashlib.sha256()
    for number in range(1, count + 1):
        digest.update(_minimal_format_example(number).encode())
    return digest.hexdigest()


def _synthetic_example_fingerprint(count: int) -> str:
    digest = hashlib.sha256()
    for task_id, prompt, suffix in _synthetic_minimal_examples(count):
        digest.update(task_id.encode())
        digest.update(prompt.encode())
        digest.update(suffix.encode())
    return digest.hexdigest()


def run(args: argparse.Namespace) -> Path:
    if args.candidates <= 0 or args.max_tokens <= 0:
        raise ValueError("candidates and max_tokens must be positive")
    if args.few_shot_k < 0:
        raise ValueError("few_shot_k must be non-negative")
    if args.few_shot_style not in {"full", "minimal_format", "synthetic_minimal"}:
        raise ValueError(f"unsupported few-shot style: {args.few_shot_style}")
    loaded_tasks = load_java_tasks(Path(args.dataset_json), args.dataset_split)
    tasks, score_dataset_path = align_tasks_to_score(
        loaded_tasks, args.score_task, args.score_split
    )
    selected = select_tasks(tasks, args.indices, args.limit)
    train_examples = []
    few_shot_example_ids = []
    if args.few_shot_k and args.few_shot_style == "full":
        train_examples = load_java_tasks(Path(args.few_shot_dataset), "train")[: args.few_shot_k]
        if len(train_examples) != args.few_shot_k:
            raise ValueError("few-shot dataset has fewer examples than few_shot_k")
        few_shot_example_ids = [example.task_id for example in train_examples]
    elif args.few_shot_k and args.few_shot_style == "minimal_format":
        few_shot_example_ids = [
            f"format_only_{number}" for number in range(1, args.few_shot_k + 1)
        ]
    elif args.few_shot_k and args.few_shot_style == "synthetic_minimal":
        few_shot_example_ids = [
            task_id for task_id, _, _ in _synthetic_minimal_examples(args.few_shot_k)
        ]
    if args.reject_io_examples:
        inspected = [("target", task) for task in selected]
        inspected.extend(("few_shot", task) for task in train_examples)
        leaked = []
        for source_name, task in inspected:
            fields = {"prompt": task.prompt, "code": task.raw.get("code", "")}
            if any(isinstance(value, str) and contains_io_examples(value) for value in fields.values()):
                leaked.append(f"{source_name}:{task.task_id}")
        if leaked:
            raise ValueError(
                "input/output examples detected while --reject_io_examples is enabled: "
                + ", ".join(leaked[:10])
            )
    target = output_directory(args.score_task, args.score_split, args.output_tag)
    if args.dry_run:
        print(
            {
                "method": "hf_matched_sampling_control",
                "model": args.model,
                "dataset_rows": len(tasks),
                "selected_rows": len(selected),
                "few_shot_k": args.few_shot_k,
                "few_shot_style": args.few_shot_style,
                "hidden_tests_exposed": False,
            }
        )
        return target

    client = build_client(args)
    writer = CandidateWriter(target, resume=args.resume)
    for task in selected:
        messages = build_messages(
            task,
            train_examples,
            args.completion_mode,
            few_shot_style=args.few_shot_style,
            minimal_few_shot_k=args.few_shot_k,
        )
        for rank in range(args.candidates):
            if args.resume and not writer.pending(task.index, rank):
                continue
            started = time.perf_counter()
            seed = args.seed + task.index * args.candidates + rank
            temperature = 0.0 if args.greedy_first and rank == 0 else args.temperature
            generated = client.generate(
                messages,
                max_tokens=args.max_tokens,
                temperature=temperature,
                top_p=args.top_p,
                seed=seed,
                stop_strings=(
                    [
                        "\nclass Main",
                        "\npublic class Main",
                        "\nComplete the following Java programming task.",
                        "\n## Solution",
                    ]
                    if args.completion_mode == "prefix_completion"
                    else None
                ),
                stop_at_java_class=(
                    args.completion_mode == "prefix_completion" or args.stop_at_java_class
                ),
            )
            source = materialize_source(task, generated.text, args.completion_mode)
            compile_started = time.perf_counter()
            compile_result = compile_java_source(
                source, timeout=args.compile_timeout, javac=args.javac or None
            )
            compile_seconds = time.perf_counter() - compile_started
            elapsed = time.perf_counter() - started
            trajectory = {
                "method": "hf_matched_sampling_control",
                "task_id": task.task_id,
                "problem_index": task.index,
                "candidate_rank": rank,
                "model": client.model_name,
                "few_shot_k": args.few_shot_k,
                "completion_mode": args.completion_mode,
                "few_shot_style": args.few_shot_style,
                "few_shot_example_ids": few_shot_example_ids,
                "hidden_tests_exposed": False,
                "input_tokens": generated.input_tokens,
                "output_tokens": generated.output_tokens,
                "raw_response": generated.text,
                "compile": dataclass_dict(compile_result),
                "elapsed_seconds": elapsed,
                "lm_seconds": elapsed - compile_seconds,
                "checker_seconds": compile_seconds,
                "completion_queries": 0,
                "rejected_tokens": [],
            }
            writer.write(task.index, rank, source, trajectory)

    writer.write_manifest(
        common_manifest(
            method="hf_matched_sampling_control",
            dataset_path=Path(args.dataset_json),
            score_dataset_path=score_dataset_path,
            args={
                key: value
                for key, value in vars(args).items()
                if key not in {"api_key"}
            }
            | {
                "few_shot_example_ids": few_shot_example_ids,
                "few_shot_examples_sha256": (
                    _example_fingerprint(train_examples)
                    if args.few_shot_style == "full"
                    else (
                        _minimal_example_fingerprint(args.few_shot_k)
                        if args.few_shot_style == "minimal_format"
                        else _synthetic_example_fingerprint(args.few_shot_k)
                    )
                ),
                "reject_io_examples": args.reject_io_examples,
            },
        )
    )
    print(f"saved candidates to {target}")
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a decoder-only zero/few-shot Java baseline.")
    parser.add_argument("--dataset_json", required=True)
    parser.add_argument("--dataset_split", default="test")
    parser.add_argument("--few_shot_dataset", default="t5_llm/data/java_mbjp_humaneval_half_train_t5.json")
    parser.add_argument("--few_shot_k", type=int, default=0)
    parser.add_argument(
        "--few_shot_style",
        choices=["full", "minimal_format", "synthetic_minimal"],
        default="full",
        help="Use train examples, format-only skeletons, or synthetic complete tasks.",
    )
    parser.add_argument(
        "--completion_mode",
        choices=["full_source", "prefix_completion"],
        default="full_source",
        help="Whether the model emits a full file or continues task.prompt's Java prefix.",
    )
    parser.add_argument(
        "--stop_at_java_class",
        action="store_true",
        help="Stop full-source generation after the first balanced Java class.",
    )
    parser.add_argument("--score_task", required=True)
    parser.add_argument("--score_split", choices=["train", "valid", "test"], default="test")
    parser.add_argument("--output_tag", required=True)
    parser.add_argument("--candidates", type=int, default=10)
    parser.add_argument("--max_tokens", type=int, default=1024)
    parser.add_argument("--compile_timeout", type=float, default=10.0)
    parser.add_argument("--javac", default="")
    parser.add_argument("--temperature", type=float, default=0.8)
    parser.add_argument("--greedy_first", action="store_true")
    parser.add_argument("--top_p", type=float, default=0.95)
    parser.add_argument("--seed", type=int, default=273567)
    parser.add_argument("--indices", default="")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--reject_io_examples",
        action="store_true",
        help="Fail closed if target or few-shot source rows contain JavaDoc I/O examples.",
    )
    parser.add_argument("--dry_run", action="store_true")
    add_model_client_arguments(parser)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
