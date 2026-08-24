from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from baselines.java_baselines.common import REPO_ROOT, sha256_file


SCORE_REPORTS = {
    "mbjp_original_test_t5gemma2_20260731": "mbjp_score.json",
    "humaneval_half_test_t5gemma2_20260731": "humaneval_score.json",
    "java_transcoder_gfg_mbjp_native_parent_safe_split80_20_t5gemma2_20260820_v14": "gfg_score.json",
}


def read_json(path: Path):
    if not path.is_file():
        raise FileNotFoundError(path)
    return json.loads(path.read_text())


def require_all_accepted(path: Path, *, negative_probe: bool = False) -> dict:
    report = read_json(path)
    if report.get("accepted") != report.get("total") or not report.get("total"):
        raise RuntimeError(f"mechanism replay did not accept every record: {path}")
    if negative_probe and not (report.get("negative_probe") or {}).get("passed"):
        raise RuntimeError(f"negative mechanism probe did not pass: {path}")
    return report


def audit(artifact_dir: Path) -> dict:
    prompt_path = artifact_dir / "prompts.json"
    response_path = artifact_dir / "responses.json"
    prompts = read_json(prompt_path)
    responses = read_json(response_path)
    tasks = prompts.get("tasks", [])
    outputs = responses.get("responses", [])
    if len(tasks) != 6 or len(outputs) != len(tasks):
        raise RuntimeError("expected exactly six ordered online smoke tasks/responses")
    allowed_prompt_keys = {
        "dataset_json",
        "dataset_sha256",
        "score_task",
        "score_split",
        "score_dataset_sha256",
        "problem_index",
        "task_id",
        "prompt",
        "prompt_sha256",
        "requested_output",
    }
    for task, output in zip(tasks, outputs):
        if set(task) != allowed_prompt_keys:
            raise RuntimeError(f"unexpected prompt-bundle fields: {set(task)}")
        if (task["task_id"], task["problem_index"]) != (
            output.get("task_id"),
            output.get("problem_index"),
        ):
            raise RuntimeError("prompt/response identity mismatch")
    mechanisms = {
        "compile": require_all_accepted(artifact_dir / "compile_report.json"),
        "syncode_parse": require_all_accepted(
            artifact_dir / "syncode_parse_report.json"
        ),
        "syncode_mask": require_all_accepted(
            artifact_dir / "syncode_mask_report_guarded.json", negative_probe=True
        ),
        "repilot_jdt": require_all_accepted(
            artifact_dir / "repilot_jdt_report_final.json", negative_probe=True
        ),
        "materialize": require_all_accepted(
            artifact_dir / "materialize_report.json"
        ),
    }
    completion_queries = sum(
        record["completion_queries"]
        for record in mechanisms["repilot_jdt"]["records"]
    )
    if completion_queries <= 0:
        raise RuntimeError("Repilot replay never exercised a JDT completion query")

    expected_problem_ids: dict[str, list[int]] = defaultdict(list)
    for task in tasks:
        expected_problem_ids[task["score_task"]].append(task["problem_index"])
    score_summaries = {}
    for score_task, filename in SCORE_REPORTS.items():
        score = read_json(artifact_dir / filename)
        expected = expected_problem_ids[score_task]
        if score.get("task") != score_task or score.get("problem_ids") != expected:
            raise RuntimeError(f"scorer scope mismatch: {filename}")
        if (
            score.get("pass1") != 1.0
            or score.get("problems") != len(expected)
            or score.get("missing") != 0
            or score.get("timeouts") != 0
            or score.get("compile_errors") != 0
        ):
            raise RuntimeError(f"functional scorer smoke failed: {filename}")
        score_summaries[score_task] = {
            "problem_ids": expected,
            "pass1": score["pass1"],
            "candidate_output_manifest_sha256": score[
                "candidate_output_manifest_sha256"
            ],
        }

    iterative_trajectory_path = (
        REPO_ROOT
        / "Utils/output/humaneval_half_test_t5gemma2_20260731_test_ans"
        / "codex_online_iterative_smoke_20260823"
        / "trajectories"
        / "39_0.json"
    )
    iterative = read_json(iterative_trajectory_path)
    compile_sequence = [round_["compile"]["success"] for round_ in iterative["rounds"]]
    if (
        compile_sequence != [False, True]
        or iterative.get("hidden_tests_exposed") is not False
        or iterative.get("model_calls") != 2
        or iterative.get("repair_calls") != 1
    ):
        raise RuntimeError("iterative compiler-feedback trajectory is incomplete")
    iterative_score = read_json(artifact_dir / "iterative_score.json")
    if iterative_score.get("pass1") != 1.0 or iterative_score.get("problem_ids") != [39]:
        raise RuntimeError("iterative repaired candidate failed the scorer")

    evidence_files = [
        prompt_path,
        response_path,
        *(artifact_dir / filename for filename in SCORE_REPORTS.values()),
        artifact_dir / "iterative_score.json",
        artifact_dir / "syncode_mask_report_guarded.json",
        artifact_dir / "repilot_jdt_report_final.json",
        iterative_trajectory_path,
    ]
    return {
        "schema_version": 1,
        "status": "passed",
        "scope": "six selected one-candidate online smoke tasks; not a benchmark result",
        "online_model": responses.get("model"),
        "hidden_tests_exposed_to_online_model": False,
        "selected_tasks": len(tasks),
        "compile_accepted": mechanisms["compile"]["accepted"],
        "syncode_parse_accepted": mechanisms["syncode_parse"]["accepted"],
        "syncode_mask_accepted": mechanisms["syncode_mask"]["accepted"],
        "syncode_negative_probe_passed": mechanisms["syncode_mask"][
            "negative_probe"
        ]["passed"],
        "repilot_accepted": mechanisms["repilot_jdt"]["accepted"],
        "repilot_completion_queries": completion_queries,
        "repilot_negative_probe_passed": mechanisms["repilot_jdt"][
            "negative_probe"
        ]["passed"],
        "iterative_compile_sequence": compile_sequence,
        "functional_scores": score_summaries,
        "evidence_sha256": {
            str(path): sha256_file(path) for path in evidence_files
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit the checkpoint-free online smoke run.")
    parser.add_argument("--artifact_dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite audit summary: {args.output}")
    summary = audit(args.artifact_dir)
    args.output.write_text(json.dumps(summary, indent=2, sort_keys=True))
    print(summary)


if __name__ == "__main__":
    main()
