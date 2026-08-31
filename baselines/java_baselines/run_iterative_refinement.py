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
    compile_java_source,
    dataclass_dict,
    extract_java_source,
    load_java_tasks,
    output_directory,
    select_tasks,
)
from baselines.java_baselines.model_clients import (
    add_model_client_arguments,
    build_client,
)
from baselines.java_baselines.prompts import initial_messages, repair_messages
from baselines.java_baselines.run_decoder_only_zero_few_shot import materialize_source


def refine_candidate(task, rank, args, client):
    rounds = []
    completion_mode = getattr(args, "completion_mode", "full_source")
    messages = (
        [{"role": "user", "content": task.prompt.rstrip()}]
        if completion_mode == "prefix_completion"
        else (
            [{"role": "user", "content": task.prompt}]
            if getattr(client, "model_family", "") == "seq2seq"
            and args.hf_seq2seq_initial_mode == "task_prefix"
            else initial_messages(task)
        )
    )
    final_source = ""
    effective_temperature = (
        0.0 if getattr(args, "greedy_first", False) and rank == 0 else args.temperature
    )
    for round_index in range(args.max_repair_rounds + 1):
        round_started = time.perf_counter()
        seed = args.seed + task.index * args.candidates + rank + round_index * 1_000_003
        generated = client.generate(
            messages,
            max_tokens=args.max_tokens_per_call,
            temperature=effective_temperature,
            top_p=args.top_p,
            seed=seed,
            stop_strings=(
                [
                    "\nclass Main",
                    "\npublic class Main",
                    "\nComplete the following Java programming task.",
                    "\n## Solution",
                ]
                if completion_mode == "prefix_completion"
                else None
            ),
            stop_at_java_class=completion_mode == "prefix_completion",
        )
        final_source = materialize_source(task, generated.text, completion_mode)
        compile_result = compile_java_source(
            final_source, timeout=args.compile_timeout, javac=args.javac or None
        )
        rounds.append(
            {
                "round": round_index,
                "seed": seed,
                "temperature": effective_temperature,
                "raw_response": generated.text,
                "source": final_source,
                "input_tokens": generated.input_tokens,
                "output_tokens": generated.output_tokens,
                "completion_mode": completion_mode,
                "compile": dataclass_dict(compile_result),
                "elapsed_seconds": time.perf_counter() - round_started,
            }
        )
        if compile_result.success or round_index == args.max_repair_rounds:
            break
        diagnostics = compile_result.diagnostics[: args.max_diagnostic_chars]
        messages = repair_messages(task, final_source, diagnostics)
    return final_source, rounds


def run(args: argparse.Namespace) -> Path:
    if not 0 <= args.max_repair_rounds <= 2:
        raise ValueError("controlled refinement permits zero, one, or two repair rounds")
    if args.candidates <= 0 or args.max_tokens_per_call <= 0:
        raise ValueError("candidates and max_tokens_per_call must be positive")
    dataset_path = Path(args.dataset_json)
    loaded_tasks = load_java_tasks(dataset_path, args.dataset_split)
    all_tasks, score_dataset_path = align_tasks_to_score(
        loaded_tasks, args.score_task, args.score_split
    )
    tasks = select_tasks(all_tasks, args.indices, args.limit)
    if args.dry_run:
        print(
            {
                "method": "compiler_feedback_refinement",
                "dataset_rows": len(all_tasks),
                "selected_rows": len(tasks),
                "hidden_tests_exposed": False,
                "score_dataset": str(score_dataset_path),
            }
        )
        return output_directory(args.score_task, args.score_split, args.output_tag)

    client = build_client(args)
    target = output_directory(args.score_task, args.score_split, args.output_tag)
    writer = CandidateWriter(target, resume=args.resume)
    for task in tasks:
        for rank in range(args.candidates):
            if args.resume and not writer.pending(task.index, rank):
                continue
            final_source, rounds = refine_candidate(task, rank, args, client)
            writer.write(
                task.index,
                rank,
                final_source,
                {
                    "method": "compiler_feedback_refinement",
                    "task_id": task.task_id,
                    "problem_index": task.index,
                    "candidate_rank": rank,
                    "model": client.model_name,
                    "completion_mode": getattr(args, "completion_mode", "full_source"),
                    "hidden_tests_exposed": False,
                    "model_calls": len(rounds),
                    "repair_calls": max(0, len(rounds) - 1),
                    "total_input_tokens": (
                        sum(round_data["input_tokens"] for round_data in rounds)
                        if all(round_data["input_tokens"] is not None for round_data in rounds)
                        else None
                    ),
                    "total_output_tokens": (
                        sum(round_data["output_tokens"] for round_data in rounds)
                        if all(round_data["output_tokens"] is not None for round_data in rounds)
                        else None
                    ),
                    "elapsed_seconds": sum(
                        round_data["elapsed_seconds"] for round_data in rounds
                    ),
                    "rounds": rounds,
                },
            )
    writer.write_manifest(
        common_manifest(
            method="compiler_feedback_refinement",
            dataset_path=dataset_path,
            score_dataset_path=score_dataset_path,
            args={
                key: value
                for key, value in vars(args).items()
                if key not in {"api_key_env"}
            },
        )
        | {
            "model": client.model_name,
            "hidden_tests_exposed": False,
            "feedback": "javac diagnostics only",
        }
    )
    print(f"saved candidates to {target}")
    return target


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Controlled Java compiler-feedback iterative refinement baseline."
    )
    parser.add_argument("--dataset_json", required=True)
    parser.add_argument("--dataset_split", default="test")
    parser.add_argument("--score_task", required=True)
    parser.add_argument("--score_split", choices=["train", "valid", "test"], default="test")
    parser.add_argument("--output_tag", required=True)
    parser.add_argument("--candidates", type=int, default=10)
    parser.add_argument("--max_repair_rounds", type=int, default=2)
    parser.add_argument("--max_tokens_per_call", type=int, default=1024)
    parser.add_argument("--max_diagnostic_chars", type=int, default=6000)
    parser.add_argument(
        "--completion_mode",
        choices=["full_source", "prefix_completion"],
        default="full_source",
        help="Whether the model emits a full file or continues the benchmark Java prefix.",
    )
    parser.add_argument("--compile_timeout", type=float, default=10.0)
    parser.add_argument("--javac", default="")
    parser.add_argument("--temperature", type=float, default=0.8)
    parser.add_argument(
        "--greedy_first",
        action="store_true",
        help="Use greedy decoding for rank 0 and sampling for later candidates.",
    )
    parser.add_argument("--top_p", type=float, default=0.95)
    parser.add_argument("--seed", type=int, default=273567)
    parser.add_argument("--indices", default="")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry_run", action="store_true")
    add_model_client_arguments(parser)
    parser.add_argument(
        "--hf_seq2seq_initial_mode",
        choices=["task_prefix", "instruction"],
        default="task_prefix",
        help="Use the frozen prefix-to-full-source contract for a seq2seq initial call.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if not args.dry_run:
        if args.backend == "scripted" and not args.scripted_responses:
            raise SystemExit("--scripted_responses is required for scripted backend")
        if args.backend != "scripted" and not args.model:
            raise SystemExit("--model is required")
    run(args)


if __name__ == "__main__":
    main()
