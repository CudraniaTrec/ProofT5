#!/usr/bin/env python3
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import pickle
import subprocess
import sys
import time


def compile_one(
    repo: Path,
    coqc: Path,
    source: Path,
    code: str,
    problem_id: int,
    attempts: int,
) -> dict:
    relative_source = source.relative_to(repo)
    last_error = ""
    for attempt in range(attempts):
        try:
            result = subprocess.run(
                [str(coqc), "-Q", "coq_model/coq_code", "PLF", str(relative_source)],
                cwd=repo,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30,
            )
            if result.returncode == 0 and result.stdout:
                return {
                    "problem_id": problem_id,
                    "coq_sha256": hashlib.sha256(code.encode("utf-8")).hexdigest(),
                    "raw_coqview": result.stdout,
                    "source_file": str(relative_source),
                }
            last_error = f"returncode={result.returncode} stderr={result.stderr[-1000:]}"
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        if attempt + 1 < attempts:
            time.sleep(1)
    raise RuntimeError(f"problem {problem_id} failed after {attempts} attempts: {last_error}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--output_dir", type=Path, required=True)
    parser.add_argument("--coqc", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=32)
    parser.add_argument("--attempts", type=int, default=3)
    args = parser.parse_args()

    repo = args.repo.resolve()
    coqc = args.coqc.resolve()
    if not coqc.is_file() or not os.access(coqc, os.X_OK):
        raise RuntimeError(f"coqc is not executable: {coqc}")
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    source_dir = output_dir / "sources"
    source_dir.mkdir(exist_ok=True)

    sys.path.insert(0, str(repo))
    os.chdir(repo)
    import beamsearch_coq
    from run import load_rules_for_task, load_tokenizer_for_task

    task_dir = repo / "Utils/data" / args.task
    config = json.loads((task_dir / "config.json").read_text(encoding="utf-8"))
    with (task_dir / "test.pkl").open("rb") as handle:
        rows = pickle.load(handle)
    if len(rows) != 641:
        raise RuntimeError(f"expected 641 rows, found {len(rows)}")
    rules = load_rules_for_task(args.task)
    tokenizer = load_tokenizer_for_task(args.task)
    beamsearch_coq.configure_runtime(rules, tokenizer_obj=tokenizer)
    pad_id = config.get("mask_id") or 0

    sources = {}
    for problem_id, row in enumerate(rows[:608]):
        prefix = [int(token) for token in row["prefix"] if int(token) != pad_id]
        node = beamsearch_coq.SearchNode(config["max_coqview_len"])
        if not prefix or prefix[0] != beamsearch_coq.rule_dict["T_ClassDecl"]:
            raise RuntimeError(f"invalid prefix start for problem {problem_id}")
        for token in prefix[1:]:
            if not node.apply(token, 0):
                raise RuntimeError(
                    f"invalid prefix token {token} for problem {problem_id}"
                )
        code = node.to_coq()
        if not code:
            raise RuntimeError(f"cannot render initial Coq for problem {problem_id}")
        # Coq derives the compilation unit name from the source basename;
        # a numeric basename such as ``0.v`` is not a valid identifier.
        source = source_dir / f"pinit_cache_{problem_id}.v"
        source.write_text(code, encoding="utf-8")
        sources[problem_id] = (source, code)

    rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(
                compile_one, repo, coqc, source, code, problem_id, args.attempts
            ): problem_id
            for problem_id, (source, code) in sources.items()
        }
        for future in concurrent.futures.as_completed(futures):
            row = future.result()
            problem_id = row["problem_id"]
            tmp_path = output_dir / f".{problem_id}.json.tmp"
            final_path = output_dir / f"{problem_id}.json"
            tmp_path.write_text(
                json.dumps(row, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            os.replace(tmp_path, final_path)
            rows.append(row)

    rows.sort(key=lambda row: row["problem_id"])
    if [row["problem_id"] for row in rows] != list(range(608)):
        raise RuntimeError("cache coverage is not exactly 0..607")
    manifest = {
        "problems": 608,
        "problem_ids": list(range(608)),
        "task": args.task,
        "coqc": str(coqc),
        "workers": args.workers,
        "attempts": args.attempts,
        "rows": [
            {
                "problem_id": row["problem_id"],
                "coq_sha256": row["coq_sha256"],
                "source_file": row["source_file"],
            }
            for row in rows
        ],
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"CACHE_OK: {len(rows)}/608 at {output_dir}")


if __name__ == "__main__":
    main()
