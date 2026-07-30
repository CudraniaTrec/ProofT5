import argparse
import json
import os
import pickle
import shutil
import subprocess
import sys
import tempfile
from multiprocessing import Pool

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from beamsearch_coq import configure_runtime
from coq_model.program_model import detokenization_wrapper


JAVA_PREFIX = """import java.lang.*;
import java.util.*;
import java.io.*;
import java.math.*;
"""


def load_pickle(path):
    with open(path, "rb") as f:
        return pickle.load(f)


def load_tokenizer(task_dir):
    for name in ["coq_tokenizer.pkl", "tokenizer.pkl"]:
        path = os.path.join(task_dir, name)
        if os.path.exists(path):
            return load_pickle(path)
    return None


def run_java_job(args):
    java_code, test_code, work_root, label, timeout = args
    folder = tempfile.mkdtemp(prefix=f"{label}_", dir=work_root)
    java_path = os.path.join(folder, "Main.java")
    with open(java_path, "w") as f:
        f.write(f"{JAVA_PREFIX}\n{java_code}\n{test_code}")
    try:
        compile_result = subprocess.run(
            ["javac", "-d", folder, java_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
        if compile_result.returncode != 0:
            return {
                "status": "compile_error",
                "message": compile_result.stderr.decode(errors="replace")[:500],
            }
        run_result = subprocess.run(
            ["java", "-cp", folder, "Main"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
        if run_result.returncode == 0:
            return {"status": "success", "message": ""}
        return {
            "status": "run_error",
            "message": (run_result.stderr or run_result.stdout).decode(errors="replace")[:500],
        }
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "message": ""}
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def row_tokens(row, id_to_token):
    if "tokens" in row and row["tokens"] and isinstance(row["tokens"][0], str):
        return row["tokens"]
    return [id_to_token[idx] for idx in row["rulelist"][1:-1]]


def validate_task(data_root, task, splits, timeout, check_java_code, workers):
    task_dir = os.path.join(data_root, task)
    rules = load_pickle(os.path.join(task_dir, "rules.pkl"))
    tokenizer = load_tokenizer(task_dir)
    if tokenizer is None:
        raise FileNotFoundError(f"No tokenizer found for {task}")
    configure_runtime(rules, tokenizer)
    id_to_token = {idx: token for token, idx in rules.items()}

    work_root = os.path.abspath(os.path.join("tmp", "validate_prooft5_data", task))
    if os.path.exists(work_root):
        shutil.rmtree(work_root)
    os.makedirs(work_root, exist_ok=True)

    summary = {"task": task, "splits": {}}
    for split in splits:
        split_path = os.path.join(task_dir, f"{split}.pkl")
        if not os.path.exists(split_path):
            continue
        rows = load_pickle(split_path)
        failures = []
        jobs = []
        for idx, row in enumerate(rows):
            if "test" not in row or "rulelist" not in row:
                continue
            tokens = row_tokens(row, id_to_token)
            program = detokenization_wrapper(tokens)
            if program is None:
                failures.append({"idx": idx, "kind": "detok", "status": "detok_error"})
                continue
            jobs.append((idx, "detok", program.to_java(), row["test"]))
            if check_java_code and "java_code" in row:
                jobs.append((idx, "java_code", row["java_code"], row["test"]))
        java_jobs = [
            (java_code, test_code, work_root, f"{split}_{idx}_{kind}", timeout)
            for idx, kind, java_code, test_code in jobs
        ]
        if java_jobs:
            with Pool(processes=workers) as pool:
                results = pool.map(run_java_job, java_jobs)
            for (idx, kind, _, _), result in zip(jobs, results):
                if result["status"] != "success":
                    failures.append({"idx": idx, "kind": kind, **result})
        summary["splits"][split] = {
            "rows": len(rows),
            "failures": failures,
            "failure_count": len(failures),
        }
    shutil.rmtree(work_root, ignore_errors=True)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_root", default="Utils/data")
    parser.add_argument("--task", action="append", required=True)
    parser.add_argument("--split", action="append", choices=["train", "valid", "test"])
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--check_java_code", action="store_true")
    parser.add_argument("--output")
    parser.add_argument("--workers", type=int, default=32)
    args = parser.parse_args()

    splits = args.split or ["train", "valid", "test"]
    summaries = [
        validate_task(args.data_root, task, splits, args.timeout, args.check_java_code, args.workers)
        for task in args.task
    ]
    text = json.dumps(summaries, indent=2)
    if args.output:
        with open(args.output, "w") as f:
            f.write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
