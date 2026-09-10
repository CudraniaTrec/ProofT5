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
    load_java_tasks,
    output_directory,
    select_tasks,
)
from baselines.java_baselines.model_clients import (
    add_model_client_arguments,
    build_client,
)
from baselines.java_baselines.prompts import repair_messages
from baselines.java_baselines.run_decoder_only_zero_few_shot import materialize_source


def repair_candidate(task, rank, initial_source, args, client):
    """Repair an existing candidate with the configured repair agent.

    Round 0 is the imported source; it is recompiled here so the trajectory
    records the exact javac verdict the repair agent responds to.  Candidates
    that already compile are kept verbatim.
    """
    rounds = []
    compile_result = compile_java_source(
        initial_source, timeout=args.compile_timeout, javac=args.javac or None
    )
    rounds.append(
        {
            "round": 0,
            "seed": None,
            "temperature": None,
            "raw_response": None,
            "source": initial_source,
            "input_tokens": None,
            "output_tokens": None,
            "completion_mode": "full_source",
            "compile": dataclass_dict(compile_result),
            "elapsed_seconds": 0.0,
        }
    )
    final_source = initial_source
    messages = None
    if not compile_result.success:
        messages = repair_messages(
            task, initial_source, compile_result.diagnostics[: args.max_diagnostic_chars]
        )
    effective_temperature = (
        0.0 if args.greedy_first and rank == 0 else args.temperature
    )
    for round_index in range(1, args.max_repair_rounds + 1):
        if messages is None:
            break
        round_started = time.perf_counter()
        seed = args.seed + task.index * args.candidates + rank + round_index * 1_000_003
        generated = client.generate(
            messages,
            max_tokens=args.max_tokens_per_call,
            temperature=effective_temperature,
            top_p=args.top_p,
            seed=seed,
        )
        final_source = materialize_source(task, generated.text, "full_source")
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
                "completion_mode": "full_source",
                "compile": dataclass_dict(compile_result),
                "elapsed_seconds": time.perf_counter() - round_started,
            }
        )
        if compile_result.success or round_index == args.max_repair_rounds:
            break
        messages = repair_messages(
            task, final_source, compile_result.diagnostics[: args.max_diagnostic_chars]
        )
    return final_source, rounds


def run(args: argparse.Namespace) -> Path:
    if not 0 <= args.max_repair_rounds <= 2:
        raise ValueError("controlled refinement permits zero, one, or two repair rounds")
    if args.candidates <= 0 or args.max_tokens_per_call <= 0:
        raise ValueError("candidates and max_tokens_per_call must be positive")
    initial_dir = Path(args.initial_dir)
    initial_manifest_path = initial_dir / "baseline_manifest.json"
    if not initial_manifest_path.exists():
        raise FileNotFoundError(f"missing initial manifest: {initial_manifest_path}")
    initial_manifest = __import__("json").loads(initial_manifest_path.read_text())

    dataset_path = Path(args.dataset_json)
    loaded_tasks = load_java_tasks(dataset_path, args.dataset_split)
    all_tasks, score_dataset_path = align_tasks_to_score(
        loaded_tasks, args.score_task, args.score_split
    )
    tasks = select_tasks(all_tasks, args.indices, args.limit)
    if args.dry_run:
        print(
            {
                "method": "compiler_feedback_repair_from_initial",
                "initial_dir": str(initial_dir),
                "initial_method": initial_manifest.get("method"),
                "dataset_rows": len(all_tasks),
                "selected_rows": len(tasks),
                "candidates": args.candidates,
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
            initial_path = initial_dir / f"{task.index}_{rank}.txt"
            if not initial_path.exists():
                raise FileNotFoundError(f"missing initial candidate: {initial_path}")
            initial_source = initial_path.read_text()
            round_started = time.perf_counter()
            final_source, rounds = repair_candidate(task, rank, initial_source, args, client)
            repair_rounds = [r for r in rounds if r["round"] > 0]
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
                    "initial_source_dir": str(initial_dir),
                    "initial_method": initial_manifest.get("method"),
                    "initial_model": initial_manifest.get("model") or initial_manifest.get("arguments", {}).get("model"),
                    "completion_mode": "full_source",
                    "hidden_tests_exposed": False,
                    "model_calls": len(repair_rounds),
                    "repair_calls": len(repair_rounds),
                    "total_input_tokens": (
                        sum(r["input_tokens"] for r in repair_rounds)
                        if repair_rounds
                        and all(r["input_tokens"] is not None for r in repair_rounds)
                        else None
                    ),
                    "total_output_tokens": (
                        sum(r["output_tokens"] for r in repair_rounds)
                        if repair_rounds
                        and all(r["output_tokens"] is not None for r in repair_rounds)
                        else None
                    ),
                    "elapsed_seconds": sum(r["elapsed_seconds"] for r in rounds),
                    "wall_seconds": time.perf_counter() - round_started,
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
            "initial_output_dir": str(initial_dir.resolve()),
            "initial_method": initial_manifest.get("method"),
            "hidden_tests_exposed": False,
            "feedback": "javac diagnostics only",
            "provenance_note": (
                "round-0 candidates imported unchanged from the ordinary matched-sampling "
                "control; rounds 1+ generated by the repair agent below"
            ),
        }
    )
    print(f"saved candidates to {target}")
    return target


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compiler-feedback repair over imported round-0 candidates: "
            "fine-tuned generator supplies round 0, a separate repair agent "
            "consumes javac diagnostics for later rounds."
        )
    )
    parser.add_argument("--initial_dir", required=True)
    parser.add_argument("--dataset_json", required=True)
    parser.add_argument("--dataset_split", default="test")
    parser.add_argument("--score_task", required=True)
    parser.add_argument("--score_split", choices=["train", "valid", "test"], default="test")
    parser.add_argument("--output_tag", required=True)
    parser.add_argument("--candidates", type=int, default=10)
    parser.add_argument("--max_repair_rounds", type=int, default=2)
    parser.add_argument("--max_tokens_per_call", type=int, default=1024)
    parser.add_argument("--max_diagnostic_chars", type=int, default=6000)
    parser.add_argument("--compile_timeout", type=float, default=10.0)
    parser.add_argument("--javac", default="")
    parser.add_argument("--temperature", type=float, default=0.8)
    parser.add_argument(
        "--greedy_first",
        action="store_true",
        help="Repair rank 0 greedily and later candidates with sampling.",
    )
    parser.add_argument("--top_p", type=float, default=0.95)
    parser.add_argument("--seed", type=int, default=273567)
    parser.add_argument("--indices", default="")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry_run", action="store_true")
    add_model_client_arguments(parser)
    return parser


def main() -> None:
    run(build_parser().parse_args())


if __name__ == "__main__":
    main()
