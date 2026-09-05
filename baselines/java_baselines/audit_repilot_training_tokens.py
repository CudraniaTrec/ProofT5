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

from transformers import AutoTokenizer

from baselines.java_baselines.common import REPO_ROOT
from baselines.java_baselines.jdt_completion import (
    RepilotJdtClient,
    discover_jdt_command,
    trivially_feasible,
)
from baselines.java_baselines.run_repilot import (
    _decoded_delta,
    longest_common_completion_prefix,
)


def run(args: argparse.Namespace) -> dict:
    active_completion_policy = getattr(
        args, "active_completion_policy", "upstream"
    )
    rows = [
        row
        for row in json.loads(Path(args.dataset).read_text())
        if row.get("type") == "train" and row.get("benchmark") == "mbjp"
    ]
    indexed = [
        (index, row)
        for index, row in enumerate(rows)
        if index % args.shard_count == args.shard_index
    ]
    tokenizer = AutoTokenizer.from_pretrained(
        args.tokenizer, local_files_only=True
    )
    java = args.java or os.environ.get("PROOFT5_JAVA") or shutil.which("java") or "java"
    java_home = Path(
        args.java_home
        or os.environ.get("PROOFT5_JAVA_HOME")
        or Path(java).resolve().parents[1]
    )
    command = discover_jdt_command(
        REPO_ROOT,
        java,
        join_completion=getattr(args, "ide_join_completion", False),
        completion_timeout_ms=(
            args.completion_timeout_ms if getattr(args, "ide_best_effort", False) else None
        ),
    )
    workspace = Path(args.workspace)
    started = time.perf_counter()
    tokens_checked = 0
    jdt_queries = 0
    trivial_bypasses = 0
    active_completion_accepts = 0
    active_completion_rejections = 0
    active_completion_fallbacks = 0
    active_completion_starts = 0
    completion_cache_hits_before = 0
    false_prunes = []
    with RepilotJdtClient(command, workspace, java_home, args.timeout) as jdt:
        completion_cache_hits_before = jdt.completion_cache_hits
        for index, row in indexed:
            prompt_ids = tokenizer(row["prompt"], return_tensors="pt")[
                "input_ids"
            ][0].tolist()
            suffix = row["code"][len(row["prompt"]) :]
            suffix_ids = tokenizer.encode(suffix, add_special_tokens=False)
            generated_ids = []
            active_completion = None
            jdt.open_document(row["prompt"])
            row_false_prune = None
            for step, token_id in enumerate(suffix_ids):
                decoded, prospective, token = _decoded_delta(
                    tokenizer, prompt_ids + generated_ids, token_id
                )
                tokens_checked += 1
                active_accept = bool(
                    args.active_completion
                    and active_completion is not None
                    and active_completion.startswith(token)
                )
                active_reject = bool(
                    args.active_completion
                    and active_completion is not None
                    and not active_completion.startswith(token)
                    and not token.startswith(active_completion)
                )
                if active_reject and active_completion_policy == "safe":
                    active_reject = False
                    active_completion = None
                    active_completion_fallbacks += 1
                continuations = None
                if active_accept:
                    jdt.update_document(prospective)
                    feasible = True
                    active_completion = active_completion[len(token) :] or None
                    active_completion_accepts += 1
                elif active_reject:
                    feasible = False
                    active_completion_rejections += 1
                elif (
                    args.policy == "upstream_trivial_bypass"
                    and trivially_feasible(token)
                ):
                    jdt.update_document(prospective)
                    feasible = True
                    trivial_bypasses += 1
                else:
                    feasible, continuations = jdt.token_feasible(decoded, token)
                    jdt_queries += 1
                    if feasible and args.active_completion and continuations:
                        next_active = longest_common_completion_prefix(continuations)
                        if next_active:
                            active_completion = next_active
                            active_completion_starts += 1
                if not feasible and row_false_prune is None:
                    row_false_prune = {
                        "dataset_index": index,
                        "task_id": row.get("task_id"),
                        "step": step,
                        "token_id": token_id,
                        "token": token,
                        "prefix_tail": decoded[-160:],
                    }
                    false_prunes.append(row_false_prune)
                generated_ids.append(token_id)
    result = {
        "audit_scope": "training-only known-correct MBJP Java suffixes",
        "dataset": args.dataset,
        "policy": args.policy,
        "shard_index": args.shard_index,
        "shard_count": args.shard_count,
        "known_correct_programs": len(indexed),
        "tokens_checked": tokens_checked,
        "jdt_queries": jdt_queries,
        "trivial_bypasses": trivial_bypasses,
        "active_completion": args.active_completion,
        "active_completion_policy": active_completion_policy,
        "active_completion_accepts": active_completion_accepts,
        "active_completion_rejections": active_completion_rejections,
        "active_completion_fallbacks": active_completion_fallbacks,
        "active_completion_starts": active_completion_starts,
        "completion_cache_hits": jdt.completion_cache_hits - completion_cache_hits_before,
        "ide_best_effort": getattr(args, "ide_best_effort", False),
        "jdt_join_completion": getattr(args, "ide_join_completion", False),
        "completion_timeout_ms": getattr(args, "completion_timeout_ms", None),
        "programs_with_false_prune": len(false_prunes),
        "false_prunes": false_prunes,
        "elapsed_seconds": time.perf_counter() - started,
        "checkpoint_or_test_selection": False,
    }
    Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.json_out).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Replay known-correct MBJP training suffixes through Repilot/JDT."
    )
    parser.add_argument(
        "--dataset", default="t5_llm/data/java_mbjp_humaneval_half_train_t5.json"
    )
    parser.add_argument("--tokenizer", default="Utils/models/t5gemma-2-1b-1b")
    parser.add_argument(
        "--policy",
        choices=["upstream_trivial_bypass", "every_token"],
        default="every_token",
    )
    parser.add_argument(
        "--active_completion",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Replay the Repilot artifact's ACTIVE=1 longest-prefix protocol.",
    )
    parser.add_argument(
        "--active_completion_policy",
        choices=["upstream", "safe"],
        default="upstream",
    )
    parser.add_argument("--shard_index", type=int, default=0)
    parser.add_argument("--shard_count", type=int, default=1)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--json_out", required=True)
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument(
        "--ide_best_effort",
        action="store_true",
        help="Use the extended JDT completion timeout and full IDE capabilities.",
    )
    parser.add_argument("--completion_timeout_ms", type=int, default=5000)
    parser.add_argument("--ide_join_completion", action="store_true")
    parser.add_argument("--java", default="")
    parser.add_argument("--java_home", default="")
    args = parser.parse_args()
    if not 0 <= args.shard_index < args.shard_count:
        raise SystemExit("shard_index must be in [0, shard_count)")
    run(args)


if __name__ == "__main__":
    main()
