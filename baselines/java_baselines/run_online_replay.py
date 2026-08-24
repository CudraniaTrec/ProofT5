from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from baselines.java_baselines.common import (
    CandidateWriter,
    REPO_ROOT,
    compile_java_source,
    output_directory,
    sha256_file,
)
from baselines.java_baselines.jdt_completion import (
    RepilotJdtClient,
    discover_jdt_command,
    trivially_feasible,
)
from baselines.java_baselines.syncode_cache_guard import (
    finalize_mask_store,
    prepare_mask_store,
)


def load_replay_inputs(prompt_bundle_path: Path, response_bundle_path: Path):
    prompts = json.loads(prompt_bundle_path.read_text())
    responses = json.loads(response_bundle_path.read_text())
    if prompts.get("schema_version") != 1:
        raise ValueError("unsupported prompt bundle schema")
    prompt_rows = prompts.get("tasks")
    response_rows = responses.get("responses")
    if not isinstance(prompt_rows, list) or not isinstance(response_rows, list):
        raise ValueError("prompt/response bundles must contain lists")
    if len(prompt_rows) != len(response_rows):
        raise ValueError("online response count does not match prompt count")
    joined = []
    for position, (prompt, response) in enumerate(zip(prompt_rows, response_rows)):
        if not isinstance(response.get("suffix"), str):
            raise ValueError(f"response {position} has no suffix")
        identity = (prompt.get("task_id"), prompt.get("problem_index"))
        response_identity = (response.get("task_id"), response.get("problem_index"))
        if identity != response_identity:
            raise ValueError(
                f"online response order/identity mismatch at {position}: "
                f"{response_identity!r} != {identity!r}"
            )
        joined.append((prompt, response, prompt["prompt"] + response["suffix"]))
    return prompts, responses, joined


def syncode_parse_records(joined) -> list[dict[str, Any]]:
    try:
        from syncode import Grammar
        from syncode.parsers import create_parser
    except ImportError as exc:
        raise RuntimeError(
            "run syncode_parse with the isolated SynCode Python 3.12 environment"
        ) from exc
    parser = create_parser(Grammar("java"), parser="lalr")
    records = []
    for prompt, _, source in joined:
        started = time.perf_counter()
        error = ""
        try:
            parser.base_parser.parse(source)
            accepted = True
        except Exception as exc:
            accepted = False
            error = f"{type(exc).__name__}: {exc}"
        records.append(
            {
                "task_id": prompt["task_id"],
                "problem_index": prompt["problem_index"],
                "accepted": accepted,
                "error": error[:4000],
                "elapsed_seconds": time.perf_counter() - started,
            }
        )
    return records


def syncode_mask_records(joined, tokenizer_path: str, mode: str):
    try:
        import torch
        from syncode import Grammar, SyncodeLogitsProcessor
        from transformers import AutoTokenizer
    except ImportError as exc:
        raise RuntimeError(
            "run syncode_mask with the isolated SynCode Python 3.12 environment"
        ) from exc
    tokenizer = AutoTokenizer.from_pretrained(
        tokenizer_path, local_files_only=True, trust_remote_code=True
    )
    grammar = Grammar("java")
    cache_path, metadata_path, cache_metadata = prepare_mask_store(
        tokenizer, grammar, mode, rebuild=False
    )
    processor = SyncodeLogitsProcessor(
        grammar=grammar,
        tokenizer=tokenizer,
        use_cache=True,
        parse_output_only=False,
        num_samples=1,
        parser="lalr",
        mode=mode,
        dev_mode=True,
    )
    finalize_mask_store(cache_path, metadata_path, cache_metadata)
    records = []
    for prompt, response, _source in joined:
        processor.reset()
        context = tokenizer(prompt["prompt"], return_tensors="pt").input_ids
        source_ids = tokenizer.encode(
            response["suffix"], add_special_tokens=False
        )
        rejected = None
        started = time.perf_counter()
        for position, token_id in enumerate(source_ids):
            next_token = torch.tensor([token_id], dtype=torch.long)
            if not processor.is_valid(context, next_token):
                rejected = {
                    "position": position,
                    "token_id": token_id,
                    "token": tokenizer.decode(
                        [token_id],
                        skip_special_tokens=False,
                        clean_up_tokenization_spaces=False,
                    ),
                }
                break
            context = torch.cat((context, next_token.unsqueeze(0)), dim=-1)
        eos_accepted = False
        if rejected is None and tokenizer.eos_token_id is not None:
            eos_accepted = processor.is_valid(
                context, torch.tensor([tokenizer.eos_token_id], dtype=torch.long)
            )
        records.append(
            {
                "task_id": prompt["task_id"],
                "problem_index": prompt["problem_index"],
                "accepted": rejected is None and eos_accepted,
                "source_tokens": len(source_ids),
                "rejected": rejected,
                "eos_accepted": eos_accepted,
                "elapsed_seconds": time.perf_counter() - started,
            }
        )
    processor.reset()
    context = tokenizer(
        "class Main { static void f() {", return_tensors="pt"
    ).input_ids
    invalid_ids = tokenizer.encode("@", add_special_tokens=False)
    invalid_accepted = True
    for token_id in invalid_ids:
        next_token = torch.tensor([token_id], dtype=torch.long)
        if not processor.is_valid(context, next_token):
            invalid_accepted = False
            break
        context = torch.cat((context, next_token.unsqueeze(0)), dim=-1)
    negative_probe = {
        "description": "invalid Java start token '@' must be masked",
        "accepted": invalid_accepted,
        "passed": not invalid_accepted,
    }
    return records, negative_probe


def repilot_records(
    joined,
    tokenizer_path: str,
    java: str,
    java_home: Path,
    timeout: float,
):
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(
        tokenizer_path, local_files_only=True, trust_remote_code=True
    )
    command = discover_jdt_command(REPO_ROOT, java)
    records = []
    negative_probe = None
    with tempfile.TemporaryDirectory(prefix="prooft5-repilot-online-replay-") as workspace:
        with RepilotJdtClient(command, Path(workspace), java_home, timeout) as jdt:
            for prompt, response, _ in joined:
                jdt.open_document(prompt["prompt"])
                accepted_suffix = ""
                rejected = None
                queries = 0
                token_ids = tokenizer.encode(response["suffix"], add_special_tokens=False)
                started = time.perf_counter()
                for position, token_id in enumerate(token_ids):
                    token = tokenizer.decode(
                        [token_id],
                        skip_special_tokens=False,
                        clean_up_tokenization_spaces=False,
                    )
                    source_prefix = prompt["prompt"] + accepted_suffix
                    if trivially_feasible(token):
                        jdt.update_document(source_prefix + token)
                        feasible, continuations = True, None
                    else:
                        queries += 1
                        feasible, continuations = jdt.token_feasible(source_prefix, token)
                    if not feasible:
                        rejected = {
                            "position": position,
                            "token_id": token_id,
                            "token": token,
                            "continuations": continuations,
                        }
                        break
                    accepted_suffix += token
                records.append(
                    {
                        "task_id": prompt["task_id"],
                        "problem_index": prompt["problem_index"],
                        "accepted": rejected is None,
                        "suffix_tokens": len(token_ids),
                        "accepted_tokens": (
                            len(token_ids) if rejected is None else rejected["position"]
                        ),
                        "completion_queries": queries,
                        "rejected": rejected,
                        "elapsed_seconds": time.perf_counter() - started,
                    }
                )
            invalid_prefix = "class Main { static void f() { Sys"
            jdt.open_document(invalid_prefix)
            invalid_accepted, continuations = jdt.token_feasible(
                invalid_prefix, "Qqqqq"
            )
            negative_probe = {
                "description": "fabricated continuation after 'Sys' must be rejected",
                "accepted": invalid_accepted,
                "passed": not invalid_accepted,
                "continuations": continuations,
            }
    return records, negative_probe


def compile_records(joined) -> list[dict[str, Any]]:
    records = []
    for prompt, _, source in joined:
        result = compile_java_source(source)
        records.append(
            {
                "task_id": prompt["task_id"],
                "problem_index": prompt["problem_index"],
                "accepted": result.success,
                "diagnostics": result.diagnostics,
                "elapsed_seconds": result.elapsed_seconds,
            }
        )
    return records


def materialize_records(
    joined,
    output_tag: str,
    prompt_bundle_path: Path,
    response_bundle_path: Path,
    model_name: str,
) -> list[dict[str, Any]]:
    writers: dict[tuple[str, str], CandidateWriter] = {}
    records = []
    for prompt, response, source in joined:
        key = (prompt["score_task"], prompt["score_split"])
        if key not in writers:
            writers[key] = CandidateWriter(output_directory(*key, output_tag))
        compile_result = compile_java_source(source)
        trajectory = {
            "method": "codex_online_text_smoke",
            "online_model": model_name,
            "task_id": prompt["task_id"],
            "problem_index": prompt["problem_index"],
            "candidate_rank": 0,
            "prompt_sha256": prompt["prompt_sha256"],
            "suffix": response["suffix"],
            "compile_success": compile_result.success,
            "compile_diagnostics": compile_result.diagnostics,
            "hidden_tests_exposed": False,
        }
        writers[key].write(prompt["problem_index"], 0, source, trajectory)
        records.append(
            {
                "score_task": key[0],
                "score_split": key[1],
                "task_id": prompt["task_id"],
                "problem_index": prompt["problem_index"],
                "accepted": compile_result.success,
                "output_path": str(
                    writers[key].candidate_path(prompt["problem_index"], 0)
                ),
            }
        )
    for (score_task, score_split), writer in writers.items():
        writer.write_manifest(
            {
                "schema_version": 1,
                "method": "codex_online_text_smoke",
                "online_model": model_name,
                "score_task": score_task,
                "score_split": score_split,
                "output_tag": output_tag,
                "candidate_count_per_selected_problem": 1,
                "selection_scope": "prompt bundle only; not a benchmark result",
                "prompt_bundle": str(prompt_bundle_path.resolve()),
                "prompt_bundle_sha256": sha256_file(prompt_bundle_path),
                "response_bundle": str(response_bundle_path.resolve()),
                "response_bundle_sha256": sha256_file(response_bundle_path),
                "hidden_tests_exposed": False,
            }
        )
    return records


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Replay test-free online Java outputs through baseline mechanisms."
    )
    parser.add_argument("--prompt_bundle", type=Path, required=True)
    parser.add_argument("--response_bundle", type=Path, required=True)
    parser.add_argument(
        "--mode",
        choices=["compile", "syncode_parse", "syncode_mask", "repilot_jdt", "materialize"],
        required=True,
    )
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--tokenizer", default="")
    parser.add_argument("--syncode_mode", choices=["grammar_mask", "grammar_strict"], default="grammar_mask")
    parser.add_argument("--output_tag", default="")
    parser.add_argument("--java", default="")
    parser.add_argument("--java_home", default="")
    parser.add_argument("--jdt_timeout", type=float, default=90.0)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.report.exists():
        raise FileExistsError(f"refusing to overwrite replay report: {args.report}")
    prompts, responses, joined = load_replay_inputs(
        args.prompt_bundle, args.response_bundle
    )
    if args.mode in {"syncode_mask", "repilot_jdt"} and not args.tokenizer:
        raise SystemExit("--tokenizer is required for token-level replay")
    if args.mode == "materialize" and not args.output_tag:
        raise SystemExit("--output_tag is required for materialization")
    negative_probe = None
    if args.mode == "compile":
        records = compile_records(joined)
    elif args.mode == "syncode_parse":
        records = syncode_parse_records(joined)
    elif args.mode == "syncode_mask":
        records, negative_probe = syncode_mask_records(
            joined, args.tokenizer, args.syncode_mode
        )
    elif args.mode == "repilot_jdt":
        java = args.java or os.environ.get("PROOFT5_JAVA") or shutil.which("java") or "java"
        java_home = Path(
            args.java_home
            or os.environ.get("PROOFT5_JAVA_HOME")
            or Path(java).resolve().parents[1]
        )
        records, negative_probe = repilot_records(
            joined, args.tokenizer, java, java_home, args.jdt_timeout
        )
    else:
        records = materialize_records(
            joined,
            args.output_tag,
            args.prompt_bundle,
            args.response_bundle,
            str(responses.get("model", "unknown-online-model")),
        )
    tokenizer_provenance = None
    if args.tokenizer:
        tokenizer_root = Path(args.tokenizer).resolve()
        tokenizer_provenance = {
            "path": str(tokenizer_root),
            "files": {
                name: sha256_file(tokenizer_root / name)
                for name in ("tokenizer.json", "tokenizer_config.json")
                if (tokenizer_root / name).is_file()
            },
        }
    upstream_lock = (
        REPO_ROOT / "baselines" / "java_baselines" / "UPSTREAM_LOCK.json"
    )
    report = {
        "schema_version": 1,
        "mode": args.mode,
        "python_version": sys.version,
        "tokenizer": tokenizer_provenance,
        "syncode_mode": (
            args.syncode_mode if args.mode.startswith("syncode") else None
        ),
        "java": java if args.mode == "repilot_jdt" else None,
        "jdt_timeout": args.jdt_timeout if args.mode == "repilot_jdt" else None,
        "upstream_lock_sha256": sha256_file(upstream_lock),
        "prompt_bundle_sha256": sha256_file(args.prompt_bundle),
        "response_bundle_sha256": sha256_file(args.response_bundle),
        "online_model": responses.get("model", "unknown-online-model"),
        "hidden_tests_exposed": False,
        "records": records,
        "accepted": sum(bool(record["accepted"]) for record in records),
        "total": len(records),
        "negative_probe": negative_probe,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True))
    print(
        {
            "mode": args.mode,
            "accepted": report["accepted"],
            "total": report["total"],
            "report": str(args.report),
        }
    )


if __name__ == "__main__":
    main()
