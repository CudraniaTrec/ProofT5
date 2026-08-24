#!/usr/bin/env python3
"""Re-audit generated Java and SuFu rows after their builders have finished."""

import argparse
import concurrent.futures
import json
import pickle
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "coq_model"))
sys.path.insert(0, str(ROOT / "SuFu"))

import program_model  # noqa: E402
import sufu_model  # noqa: E402
from build_java_external_datasets import validate_java  # noqa: E402
from build_sufu_synthetic_dataset import extract_scalars, run_executor  # noqa: E402


DEFAULT_TASKS = [
    "java_humaneval_external_t5gemma2_20260730",
    "java_mceval_external_t5gemma2_20260730",
    "java_naturalcodebench_external_t5gemma2_20260730",
    "java_mathqa_external_t5gemma2_20260730",
    "sufu_synthetic_external_t5gemma2_20260730",
    "sufu_synthetic_structural_v2_t5gemma2_20260730",
]


def load_pickle(path):
    with Path(path).open("rb") as f:
        return pickle.load(f)


def audit_java(task_dir, rows, tokenizer, rules, timeout, workers):
    program_model.tokenizer = tokenizer
    def audit_one(index_row):
        index, row = index_row
        try:
            tokens = row["tokens"]
            ids = [rules[token] for token in tokens]
            if row["rulelist"] != [
                tokenizer.bos_token_id,
                *ids,
                tokenizer.eos_token_id,
            ]:
                raise RuntimeError("stored IDs do not encode stored tokens")
            program = program_model.detokenization_wrapper(tokens)
            if program is None:
                raise RuntimeError("detokenization failed")
            encoded_again = program.to_coq().tokenization()
            if encoded_again != tokens:
                raise RuntimeError("encode(decode(tokens)) changed the sequence")
            validate_java(row["java_code"], row["test"], timeout)
            return None
        except Exception as exc:
            return {
                "index": index,
                "task_id": row.get("task_id"),
                "error": f"{type(exc).__name__}: {exc}"[:1000],
            }

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        results = executor.map(audit_one, enumerate(rows))
        return [result for result in results if result is not None]


def audit_sufu(task_dir, rows, tokenizer, rules, timeout):
    grammar_tokenizer = sufu_model.tokenizer
    reverse_rules = {value: key for key, value in rules.items()}
    failures = []
    for index, row in enumerate(rows):
        try:
            tokens = [reverse_rules[token] for token in row["rulelist"][1:-1]]
            program, _ = sufu_model.detokenize(tokens)
            encoded_again = program.tokenize()
            encoded_again = grammar_tokenizer.convert_ids_to_tokens(
                grammar_tokenizer.convert_tokens_to_ids(encoded_again)
            )
            if encoded_again != tokens:
                raise RuntimeError("encode(decode(tokens)) changed the sequence")
            prefix = row["prefix"]
            if row["rulelist"][1:-1][:len(prefix)] != prefix:
                raise RuntimeError("prefix is not the target token head")
            output = run_executor(
                f"{program.to_str({})}\n{row['tests']}",
                timeout,
            )
            expected = extract_scalars(row["output"])
            actual = extract_scalars(output)
            if actual[-len(expected):] != expected:
                raise RuntimeError(
                    f"reconstructed output mismatch: {actual[-len(expected):]} != {expected}"
                )
        except Exception as exc:
            failures.append(
                {
                    "index": index,
                    "task_id": row.get("file_name"),
                    "error": f"{type(exc).__name__}: {exc}"[:1000],
                }
            )
    return failures


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, default=ROOT / "Utils" / "data")
    parser.add_argument("--task", action="append")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--workers", type=int, default=24)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main():
    args = parse_args()
    summaries = []
    for task in args.task or DEFAULT_TASKS:
        task_dir = args.data_root / task
        rows = load_pickle(task_dir / "test.pkl")
        tokenizer = load_pickle(task_dir / "tokenizer.pkl")
        rules = load_pickle(task_dir / "rules.pkl")
        if rows and "java_code" in rows[0]:
            failures = audit_java(
                task_dir, rows, tokenizer, rules, args.timeout, args.workers
            )
            language = "java"
        else:
            failures = audit_sufu(
                task_dir, rows, tokenizer, rules, args.timeout
            )
            language = "sufu"
        summary = {
            "task": task,
            "language": language,
            "rows": len(rows),
            "passed": len(rows) - len(failures),
            "failure_count": len(failures),
            "failures": failures,
        }
        summaries.append(summary)
        print(
            f"{task}: {summary['passed']}/{summary['rows']} "
            "round-trip and execution checks passed"
        )

    text = json.dumps(summaries, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n")
    if any(summary["failure_count"] for summary in summaries):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
