import argparse
import hashlib
import json
import os
import pickle
import shutil
import subprocess
from multiprocessing import Pool


REPO_ROOT = os.path.abspath(os.path.dirname(__file__))
SUFU_EXECUTOR_PATH = os.environ.get(
    "PROOFT5_SUFU_EXECUTOR",
    os.path.join(REPO_ROOT, "SuFu/SuFu/surface/f"),
)
OCAMLRUN_PATH = shutil.which("ocamlrun")
SUFU_EXECUTOR_CMD = (
    [OCAMLRUN_PATH, SUFU_EXECUTOR_PATH] if OCAMLRUN_PATH else [SUFU_EXECUTOR_PATH]
)
WORKDIR_COMPONENT_LIMIT = 120


def score_work_root(task, split, output_tag, selection_scope="all"):
    # Different subsets of the same generated output may be scored in
    # parallel.  Keep their executor sandboxes disjoint so one scorer cannot
    # delete another scorer's files during initial cleanup.
    raw_name = f"{task}_{split}_{output_tag}_{selection_scope}"
    digest = hashlib.sha256(raw_name.encode("utf-8")).hexdigest()[:16]
    readable = "".join(
        char if char.isalnum() or char in "._-" else "_" for char in raw_name
    )
    readable_limit = WORKDIR_COMPONENT_LIMIT - len(digest) - 1
    readable = readable[:readable_limit].rstrip("._-") or "score"
    component = f"{readable}_{digest}"
    return os.path.join(REPO_ROOT, "tmp", "no_write_sufu_score", component)


def error_solution(code):
    if "IndexError" in code:
        return True
    if "GrammarError" in code:
        return False
    if "??" in code:
        return True
    return False


def replace_ptree(code):
    lines = [line.strip() for line in code.splitlines() if line.strip()]
    for idx in range(len(lines) - 1):
        if lines[idx].startswith("Inductive PTree") and lines[idx + 1].startswith(
            "Inductive PList"
        ):
            lines[idx] = lines[idx][:-1]
            lines[idx + 1] = lines[idx + 1].replace("Inductive", "with")
            break
    return "\n".join(lines)


def read_candidate(output_dir, idx, cand_idx):
    for ext in ("java", "txt"):
        path = os.path.join(output_dir, f"{idx}_{cand_idx}.{ext}")
        if os.path.exists(path):
            return path, open(path, "r").read()
    return None, None


def compare_executor_output(actual, expected, test_code, test_results_only=False):
    if not test_results_only:
        return actual == expected
    test_count = sum(
        1 for line in test_code.splitlines() if line.strip().endswith(";")
    )
    if test_count <= 0:
        raise ValueError("cannot compare test results without test statements")
    actual_lines = [line.strip() for line in actual.splitlines() if line.strip()]
    expected_lines = [line.strip() for line in expected.splitlines() if line.strip()]
    if len(actual_lines) < test_count or len(expected_lines) < test_count:
        return False
    return actual_lines[-test_count:] == expected_lines[-test_count:]


def test_candidate(job):
    (
        idx,
        cand_idx,
        output_dir,
        test_code,
        expected_output,
        work_root,
        timeout,
        test_results_only,
    ) = job
    path, gen_code = read_candidate(output_dir, idx, cand_idx)
    if path is None:
        return idx, cand_idx, "missing"
    if error_solution(gen_code):
        return idx, cand_idx, "ignored"

    gen_code = replace_ptree(gen_code)
    folder = os.path.join(work_root, f"p{idx}_k{cand_idx}")
    os.makedirs(folder, exist_ok=True)
    test_path = os.path.join(folder, "test.f")
    full_code = f"{gen_code}\n{test_code}"
    with open(test_path, "w") as f:
        f.write(full_code)

    try:
        run = subprocess.run(
            SUFU_EXECUTOR_CMD + [test_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
        if run.returncode == 0:
            output = run.stdout.decode("unicode_escape", errors="replace")
            return (
                idx,
                cand_idx,
                "success"
                if compare_executor_output(
                    output,
                    expected_output,
                    test_code,
                    test_results_only=test_results_only,
                )
                else "failed",
            )

        with open(test_path, "w") as f:
            f.write(gen_code)
        partial = subprocess.run(
            SUFU_EXECUTOR_CMD + [test_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
        stderr = partial.stderr.decode("unicode_escape", errors="replace")
        if partial.returncode != 0 and "Parse error" not in stderr:
            return idx, cand_idx, "compile_error"
        return idx, cand_idx, "failed"
    except subprocess.TimeoutExpired:
        return idx, cand_idx, "timeout"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--split", choices=["train", "valid", "test"], required=True)
    parser.add_argument("--output_tag", required=True)
    parser.add_argument("--pass_at_k", type=int, default=10)
    parser.add_argument("--workers", type=int, default=32)
    parser.add_argument("--timeout", type=float, default=1.0)
    parser.add_argument(
        "--compare_test_results_only",
        action="store_true",
        help=(
            "Compare only the trailing interpreter results produced by test "
            "statements, ignoring declarations and generated identifier names."
        ),
    )
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
    parser.add_argument("--json_out", default="")
    args = parser.parse_args()

    if not os.path.isfile(SUFU_EXECUTOR_PATH):
        raise FileNotFoundError(f"SuFu executor not found: {SUFU_EXECUTOR_PATH}")
    if not OCAMLRUN_PATH:
        raise FileNotFoundError("ocamlrun not found on PATH")

    data = pickle.load(open(f"Utils/data/{args.task}/{args.split}.pkl", "rb"))
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
            int(value)
            for value in args.indices.split(",")
            if value.strip()
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
        idx for idx in selected_indices if read_candidate(output_dir, idx, 0)[0] is None
    ]

    jobs = []
    for idx in selected_indices:
        row = data[idx]
        for cand_idx in range(args.pass_at_k):
            jobs.append(
                (
                    idx,
                    cand_idx,
                    output_dir,
                    row["tests"],
                    row["output"],
                    work_root,
                    args.timeout,
                    args.compare_test_results_only,
                )
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
        total_tested += sum(1 for status in statuses if status not in {"missing", "ignored"})
        success_positions = [cand_idx for cand_idx, status in per_problem[idx] if status == "success"]
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
        "problems": prob_cnt,
        "problem_ids": selected_indices,
        "pass_at_k": args.pass_at_k,
        "output_comparison": (
            "test_results_only" if args.compare_test_results_only else "full_stdout"
        ),
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

    print(f"Task: {args.task}")
    print(f"Split: {args.split}")
    print(f"Output tag: {args.output_tag}")
    print(f"Executor: {' '.join(SUFU_EXECUTOR_CMD)}")
    print(f"Problems: {prob_cnt}")
    if args.only_completed_top0:
        print("Mode: only_completed_top0")
    print(f"Candidates per problem: {args.pass_at_k}")
    print(f"pass@1: {pass1 * 100:.2f}% ({len(top1_solved)}/{prob_cnt})")
    print(f"pass@{args.pass_at_k}: {passk * 100:.2f}% ({len(solved)}/{prob_cnt})")
    print(
        f"Compilation error rate: {ce_rate * 100:.2f}% "
        f"({compile_errors}/{total_tested})"
    )
    print(f"Average first success position: {avg_first:.2f}")
    print(f"Average candidate success rate: {avg_success_rate * 100:.2f}%")
    print(f"Missing candidates: {missing}")
    print(f"Missing problem outputs: {len(missing_problem_output_ids)}")
    print(f"Ignored candidates: {ignored}")
    print(f"Timeout candidates: {timeouts}")
    print(f"pass@1 solved ids: {top1_solved}")
    print(f"pass@{args.pass_at_k} solved ids: {solved}")

    if args.json_out:
        with open(args.json_out, "w") as f:
            json.dump(summary, f, indent=2)

    if not args.keep_workdir:
        shutil.rmtree(work_root, ignore_errors=True)


if __name__ == "__main__":
    main()
