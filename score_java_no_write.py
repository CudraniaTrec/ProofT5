import argparse
import hashlib
import json
import os
import pickle
import shutil
import subprocess
from multiprocessing import Pool


JAVA_PREFIX = """import java.lang.*;
import java.util.*;
import java.io.*;
import java.math.*;
"""
WORKDIR_COMPONENT_LIMIT = 120
JAVAC_PATH = os.environ.get("PROOFT5_JAVAC", shutil.which("javac") or "")
JAVA_PATH = os.environ.get("PROOFT5_JAVA", shutil.which("java") or "")


def resolved_java_home():
    configured = os.environ.get("PROOFT5_JAVA_HOME")
    if configured:
        return configured
    if JAVA_PATH:
        return os.path.dirname(os.path.dirname(os.path.realpath(JAVA_PATH)))
    return ""


def java_tool_env():
    env = os.environ.copy()
    jre_lib = os.path.join(resolved_java_home(), "lib")
    if os.path.isdir(jre_lib):
        current = env.get("LD_LIBRARY_PATH", "")
        env["LD_LIBRARY_PATH"] = jre_lib if not current else f"{jre_lib}:{current}"
    return env


def tool_version(command):
    run = subprocess.run(
        [command, "-version"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=java_tool_env(),
        check=True,
    )
    return (run.stdout or run.stderr).decode("utf-8", errors="replace").strip()


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_benchmark_source(data, source_rows, comparison):
    """Verify that transformed model inputs still denote the frozen Java tasks."""
    if comparison == "exact":
        if data != source_rows:
            raise RuntimeError(
                "evaluated dataset rows differ from the frozen benchmark source"
            )
        return {"mode": comparison, "verified": True, "fields": ["all"]}

    if comparison != "java_eval_semantics":
        raise ValueError(f"unsupported benchmark source comparison: {comparison}")
    if len(data) != len(source_rows):
        raise RuntimeError(
            "evaluated dataset length differs from the frozen benchmark source: "
            f"{len(data)} != {len(source_rows)}"
        )
    fields = ("benchmark", "original_split", "test")
    mismatches = []
    for idx, (row, source_row) in enumerate(zip(data, source_rows)):
        for field in fields:
            if row.get(field) != source_row.get(field):
                mismatches.append({"index": idx, "field": field})
                if len(mismatches) >= 20:
                    break
        if len(mismatches) >= 20:
            break
    if mismatches:
        raise RuntimeError(
            "evaluated dataset differs from the frozen benchmark in Java scoring "
            f"semantics: {mismatches}"
        )
    return {
        "mode": comparison,
        "verified": True,
        "fields": list(fields),
        "rows": len(data),
    }


def score_work_root(task, split, output_tag, selection_scope="all"):
    # Different subsets of the same generated output may be scored in
    # parallel.  Keep their compiler sandboxes disjoint so one scorer cannot
    # remove another scorer's files during its initial cleanup.
    raw_name = f"{task}_{split}_{output_tag}_{selection_scope}"
    digest = hashlib.sha256(raw_name.encode("utf-8")).hexdigest()[:16]
    readable = "".join(
        char if char.isalnum() or char in "._-" else "_" for char in raw_name
    )
    readable_limit = WORKDIR_COMPONENT_LIMIT - len(digest) - 1
    readable = readable[:readable_limit].rstrip("._-") or "score"
    return os.path.abspath(f"tmp/no_write_java_score/{readable}_{digest}")


def read_candidate(path):
    text = open(path, "r").read()
    # Generation workers historically wrote this exact exception line when a
    # candidate slot was unavailable.  Do not discard a real model response
    # merely because its explanation mentions Python's ``IndexError``.
    if text.strip().startswith("IndexError:") and "\n" not in text.strip():
        return None
    if "GrammarError" in text:
        return text
    lines = text.splitlines()
    if lines and (lines[0].startswith("//") or lines[0].startswith("ex:")):
        return "\n".join(lines[1:])
    return text


def candidate_output_manifest_sha256(output_dir, problem_ids, pass_at_k):
    """Hash every fixed candidate slot, including explicit missing markers."""
    digest = hashlib.sha256()
    for idx in problem_ids:
        for cand_idx in range(pass_at_k):
            java_path = os.path.join(output_dir, f"{idx}_{cand_idx}.java")
            text_path = os.path.join(output_dir, f"{idx}_{cand_idx}.txt")
            if os.path.isfile(java_path):
                path, suffix = java_path, ".java"
            elif os.path.isfile(text_path):
                path, suffix = text_path, ".txt"
            else:
                digest.update(f"{idx}_{cand_idx} MISSING\n".encode())
                continue
            content = hashlib.sha256()
            with open(path, "rb") as handle:
                for block in iter(lambda: handle.read(1024 * 1024), b""):
                    content.update(block)
            digest.update(
                f"{idx}_{cand_idx}{suffix} {os.path.getsize(path)} "
                f"{content.hexdigest()}\n".encode()
            )
    return digest.hexdigest()


def test_candidate(args):
    idx, cand_idx, output_dir, test_code, work_root, timeout = args
    path = os.path.join(output_dir, f"{idx}_{cand_idx}.java")
    if not os.path.exists(path):
        path = os.path.join(output_dir, f"{idx}_{cand_idx}.txt")
    if not os.path.exists(path):
        return idx, cand_idx, "missing"

    gen_code = read_candidate(path)
    if gen_code is None:
        return idx, cand_idx, "ignored"

    folder = os.path.join(work_root, f"p{idx}_k{cand_idx}")
    os.makedirs(folder, exist_ok=True)
    java_path = os.path.join(folder, "Main.java")
    full_code = f"{JAVA_PREFIX}\n{gen_code}\n{test_code}"
    with open(java_path, "w") as f:
        f.write(full_code)

    try:
        res = subprocess.run(
            [JAVAC_PATH, "-d", folder, java_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            env=java_tool_env(),
        )
        if res.returncode != 0:
            partial_code = f"{JAVA_PREFIX}\n{gen_code}"
            with open(java_path, "w") as f:
                f.write(partial_code)
            partial = subprocess.run(
                [JAVAC_PATH, "-d", folder, java_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                env=java_tool_env(),
            )
            error_message = partial.stderr.decode("unicode_escape", errors="replace")
            if (
                "missing return statement" in error_message
                or "unreachable statement" in error_message
                or "is already defined" in error_message
                or partial.returncode == 0
                or "?" in partial_code
            ):
                return idx, cand_idx, "failed"
            return idx, cand_idx, "compile_error"

        run = subprocess.run(
            [JAVA_PATH, "-cp", folder, "Main"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            env=java_tool_env(),
        )
        return idx, cand_idx, "success" if run.returncode == 0 else "failed"
    except subprocess.TimeoutExpired:
        return idx, cand_idx, "timeout"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--split", choices=["train", "valid", "test"], required=True)
    parser.add_argument("--output_tag", required=True)
    parser.add_argument("--pass_at_k", type=int, default=10)
    parser.add_argument("--workers", type=int, default=64)
    parser.add_argument("--timeout", type=float, default=1.0)
    parser.add_argument("--only_completed_top0", action="store_true")
    parser.add_argument("--indices", default="")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--keep_workdir", action="store_true")
    parser.add_argument("--model_output_task", default="")
    parser.add_argument("--model_type", default="")
    parser.add_argument("--train_time", default="")
    parser.add_argument("--checkpoint_epoch", type=int, default=None)
    parser.add_argument("--model_checkpoint_path", default="")
    parser.add_argument("--model_checkpoint_sha256", default="")
    parser.add_argument("--decoder", default="")
    parser.add_argument("--beam_size", type=int, default=0)
    parser.add_argument("--length_penalty", type=float, default=None)
    parser.add_argument("--generation_max_length", type=int, default=0)
    parser.add_argument("--candidate_multiplier", type=int, default=0)
    parser.add_argument("--benchmark_source_path", default="")
    parser.add_argument(
        "--benchmark_source_comparison",
        choices=["exact", "java_eval_semantics"],
        default="exact",
    )
    parser.add_argument("--json_out", default="")
    args = parser.parse_args()

    if not JAVAC_PATH or not os.path.isfile(JAVAC_PATH):
        raise FileNotFoundError(f"javac not found: {JAVAC_PATH}")
    if not JAVA_PATH or not os.path.isfile(os.path.realpath(JAVA_PATH)):
        raise FileNotFoundError(f"java not found: {JAVA_PATH}")
    javac_version = tool_version(JAVAC_PATH)
    java_version = tool_version(JAVA_PATH)

    dataset_pickle_path = os.path.abspath(
        f"Utils/data/{args.task}/{args.split}.pkl"
    )
    data = pickle.load(open(dataset_pickle_path, "rb"))
    benchmark_source_path = ""
    benchmark_source_sha256 = ""
    benchmark_source_verified_equal = False
    benchmark_source_verification = None
    if args.benchmark_source_path:
        benchmark_source_path = os.path.abspath(args.benchmark_source_path)
        if not os.path.isfile(benchmark_source_path):
            raise FileNotFoundError(benchmark_source_path)
        if benchmark_source_path.endswith(".json"):
            source_rows = json.load(open(benchmark_source_path))
        elif benchmark_source_path.endswith(".pkl"):
            source_rows = pickle.load(open(benchmark_source_path, "rb"))
        else:
            raise ValueError("benchmark source must be a .json or .pkl file")
        benchmark_source_verification = verify_benchmark_source(
            data, source_rows, args.benchmark_source_comparison
        )
        benchmark_source_sha256 = sha256_file(benchmark_source_path)
        benchmark_source_verified_equal = (
            args.benchmark_source_comparison == "exact"
        )
    output_dir = f"Utils/output/{args.task}_{args.split}_ans/{args.output_tag}"
    if not os.path.isdir(output_dir):
        raise FileNotFoundError(output_dir)

    selection_scope = json.dumps(
        {
            "indices": args.indices,
            "limit": args.limit,
            "only_completed_top0": args.only_completed_top0,
            "pass_at_k": args.pass_at_k,
        },
        sort_keys=True,
    )
    work_root = score_work_root(args.task, args.split, args.output_tag, selection_scope)
    if os.path.exists(work_root):
        shutil.rmtree(work_root)
    os.makedirs(work_root, exist_ok=True)

    selected_indices = list(range(len(data)))
    if args.indices:
        selected_indices = [
            int(value) for value in args.indices.split(",") if value.strip()
        ]
        invalid = [idx for idx in selected_indices if idx < 0 or idx >= len(data)]
        if invalid:
            raise ValueError(f"Out-of-range indices: {invalid}")
    if args.only_completed_top0:
        selected_indices = [
            idx
            for idx in selected_indices
            if os.path.exists(os.path.join(output_dir, f"{idx}_0.txt"))
            or os.path.exists(os.path.join(output_dir, f"{idx}_0.java"))
        ]
    if args.limit:
        selected_indices = selected_indices[: args.limit]

    missing_problem_output_ids = [
        idx
        for idx in selected_indices
        if not (
            os.path.exists(os.path.join(output_dir, f"{idx}_0.txt"))
            or os.path.exists(os.path.join(output_dir, f"{idx}_0.java"))
        )
    ]

    jobs = []
    for idx in selected_indices:
        row = data[idx]
        for cand_idx in range(args.pass_at_k):
            jobs.append(
                (idx, cand_idx, output_dir, row["test"], work_root, args.timeout)
            )

    with Pool(processes=args.workers) as pool:
        raw_results = pool.map(test_candidate, jobs)

    per_problem = {idx: [] for idx in selected_indices}
    for idx, cand_idx, status in raw_results:
        per_problem[idx].append((cand_idx, status))
    for values in per_problem.values():
        values.sort()

    solved = []
    top1_solved = []
    compile_errors = 0
    total_tested = 0
    missing = 0
    ignored = 0
    timeouts = 0
    first_success_pos = []
    avg_candidate_success_num = 0
    timeout_candidate_ids = []
    compile_error_candidate_ids = []

    for idx in selected_indices:
        statuses = [status for _, status in per_problem[idx]]
        missing += statuses.count("missing")
        ignored += statuses.count("ignored")
        timeouts += statuses.count("timeout")
        compile_errors += statuses.count("compile_error")
        total_tested += sum(1 for s in statuses if s not in {"missing", "ignored"})
        success_positions = [
            cand_idx
            for cand_idx, status in per_problem[idx]
            if status == "success"
        ]
        avg_candidate_success_num += len(success_positions)
        timeout_candidate_ids.extend(
            [idx, cand_idx]
            for cand_idx, status in per_problem[idx]
            if status == "timeout"
        )
        compile_error_candidate_ids.extend(
            [idx, cand_idx]
            for cand_idx, status in per_problem[idx]
            if status == "compile_error"
        )
        if success_positions:
            solved.append(idx)
            first_success_pos.append(success_positions[0])
            if success_positions[0] == 0:
                top1_solved.append(idx)
        else:
            first_success_pos.append(args.pass_at_k)

    prob_cnt = len(selected_indices)
    pass1 = len(top1_solved) / prob_cnt if prob_cnt else 0.0
    passk = len(solved) / prob_cnt if prob_cnt else 0.0
    ce_rate = compile_errors / total_tested if total_tested else 0.0
    avg_first = sum(first_success_pos) / prob_cnt if prob_cnt else 0.0
    avg_success_rate = avg_candidate_success_num / total_tested if total_tested else 0.0

    print(f"Task: {args.task}")
    print(f"Split: {args.split}")
    print(f"Output tag: {args.output_tag}")
    print(f"javac: {JAVAC_PATH} ({javac_version})")
    print(f"java: {JAVA_PATH} ({java_version.splitlines()[0]})")
    print(f"Problems: {prob_cnt}")
    if args.only_completed_top0:
        print("Mode: only_completed_top0")
    print(f"Candidates per problem: {args.pass_at_k}")
    print(f"pass@1: {pass1 * 100:.2f}% ({len(top1_solved)}/{prob_cnt})")
    print(f"pass@{args.pass_at_k}: {passk * 100:.2f}% ({len(solved)}/{prob_cnt})")
    print(f"Compilation error rate: {ce_rate * 100:.2f}% ({compile_errors}/{total_tested})")
    print(f"Average first success position: {avg_first:.2f}")
    print(f"Average candidate success rate: {avg_success_rate * 100:.2f}%")
    print(f"Missing candidates: {missing}")
    print(f"Missing problem outputs: {len(missing_problem_output_ids)}")
    print(f"Ignored candidates: {ignored}")
    print(f"Timeout candidates: {timeouts}")
    print(f"pass@1 solved ids: {top1_solved}")
    print(f"pass@{args.pass_at_k} solved ids: {solved}")

    summary = {
        "task": args.task,
        "split": args.split,
        "output_tag": args.output_tag,
        "model_output_task": args.model_output_task,
        "model_type": args.model_type,
        "train_time": args.train_time,
        "checkpoint_epoch": args.checkpoint_epoch,
        "model_checkpoint_path": args.model_checkpoint_path,
        "model_checkpoint_sha256": args.model_checkpoint_sha256,
        "generation": {
            "decoder": args.decoder or None,
            "beam_size": args.beam_size or None,
            "length_penalty": args.length_penalty,
            "generation_max_length": args.generation_max_length or None,
            "candidate_multiplier": args.candidate_multiplier or None,
        },
        "javac_path": JAVAC_PATH,
        "javac_version": javac_version,
        "java_path": JAVA_PATH,
        "java_version": java_version,
        "candidate_timeout_seconds": args.timeout,
        "problems": prob_cnt,
        "problem_ids": selected_indices,
        "dataset_pickle_path": dataset_pickle_path,
        "dataset_pickle_sha256": sha256_file(dataset_pickle_path),
        "benchmark_source_path": benchmark_source_path,
        "benchmark_source_sha256": benchmark_source_sha256,
        "benchmark_source_verified_equal": benchmark_source_verified_equal,
        "benchmark_source_verification": benchmark_source_verification,
        "candidate_output_dir": os.path.abspath(output_dir),
        "candidate_output_manifest_sha256": candidate_output_manifest_sha256(
            output_dir, selected_indices, args.pass_at_k
        ),
        "pass_at_k": args.pass_at_k,
        "pass1": pass1,
        f"pass{args.pass_at_k}": passk,
        "compile_error_rate": ce_rate,
        "compile_errors": compile_errors,
        "total_tested": total_tested,
        "average_first_success_position": avg_first,
        "average_candidate_success_rate": avg_success_rate,
        "missing": missing,
        "missing_problem_outputs": len(missing_problem_output_ids),
        "missing_problem_output_ids": missing_problem_output_ids,
        "ignored": ignored,
        "timeouts": timeouts,
        "timeout_candidate_ids": timeout_candidate_ids,
        "compile_error_candidate_ids": compile_error_candidate_ids,
        "top1_solved": top1_solved,
        "solved": solved,
        "first_success_pos": first_success_pos,
    }
    if args.json_out:
        with open(args.json_out, "w") as handle:
            json.dump(summary, handle, indent=2, sort_keys=True)

    if not args.keep_workdir:
        shutil.rmtree(work_root, ignore_errors=True)


if __name__ == "__main__":
    main()
