from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any


def _sum_present(rows: list[dict[str, Any]], key: str) -> int | float | None:
    values = [row.get(key) for row in rows]
    if not values or any(value is None for value in values):
        return None
    return sum(values)


def _observed_sum(rows: list[dict[str, Any]], key: str) -> tuple[int | float, int]:
    """Return the auditable lower-bound sum and number of observed values."""
    values = [row.get(key) for row in rows if row.get(key) is not None]
    return sum(values), len(values)


def summarize(output_dir: Path) -> dict[str, Any]:
    trajectory_dir = output_dir / "trajectories"
    paths = sorted(trajectory_dir.glob("*.json"))
    if not paths:
        raise FileNotFoundError(f"no trajectories found under {trajectory_dir}")
    rows = [json.loads(path.read_text()) for path in paths]
    elapsed = [float(row["elapsed_seconds"]) for row in rows]
    methods = {row.get("method") for row in rows}
    if len(methods) != 1:
        raise RuntimeError(f"mixed trajectory methods: {sorted(methods)}")
    method = methods.pop()
    manifest_path = output_dir / "baseline_manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.is_file() else {}
    run_args = manifest.get("arguments", manifest.get("args", {}))
    summary: dict[str, Any] = {
        "method": method,
        "candidate_count": len(rows),
        "elapsed_seconds_total": sum(elapsed),
        "elapsed_seconds_mean": statistics.mean(elapsed),
        "elapsed_seconds_median": statistics.median(elapsed),
        "runtime_timing": manifest.get("runtime_timing"),
    }
    if method in {"repilot_jdt_token_pruning", "hf_matched_sampling_control"}:
        token_cap = run_args.get("max_new_tokens")
        output_tokens = _sum_present(rows, "output_tokens")
        completion_queries = sum(row["completion_queries"] for row in rows)
        checker_seconds = _sum_present(rows, "checker_seconds")
        summary.update(
            input_tokens_total=_sum_present(rows, "input_tokens"),
            output_tokens_total=output_tokens,
            completion_queries_total=completion_queries,
            jdt_query_policy=run_args.get("jdt_query_policy"),
            trivial_bypasses_total=sum(row.get("trivial_bypasses", 0) for row in rows),
            constraint_support_expansions_total=sum(
                row.get("constraint_support_expansions", 0) for row in rows
            ),
            active_completion_enabled=run_args.get("active_completion"),
            active_completion_starts_total=sum(
                row.get("active_completion_starts", 0) for row in rows
            ),
            active_completion_accepts_total=sum(
                row.get("active_completion_accepts", 0) for row in rows
            ),
            active_completion_rejections_total=sum(
                row.get("active_completion_rejections", 0) for row in rows
            ),
            lm_seconds_total=_sum_present(rows, "lm_seconds"),
            jdt_query_seconds_total=_sum_present(rows, "jdt_query_seconds"),
            jdt_document_seconds_total=_sum_present(rows, "jdt_document_seconds"),
            checker_seconds_total=checker_seconds,
            completion_queries_per_output_token=(
                completion_queries / output_tokens if output_tokens else None
            ),
            checker_seconds_per_output_token=(
                checker_seconds / output_tokens
                if checker_seconds is not None and output_tokens
                else None
            ),
            rejected_tokens_total=sum(len(row["rejected_tokens"]) for row in rows),
            candidates_with_rejection=sum(bool(row["rejected_tokens"]) for row in rows),
            output_token_cap=token_cap,
            candidates_hitting_output_cap=(
                sum(
                    row.get("output_tokens") is not None
                    and row["output_tokens"] >= token_cap
                    for row in rows
                )
                if token_cap is not None
                else None
            ),
        )
    elif method in {
        "syncode_java_cfg",
        "syncode_java_cfg_proposal_preserving_rejection",
    }:
        token_cap = run_args.get("max_new_tokens")
        observed_input_tokens, observed_input_count = _observed_sum(rows, "input_tokens")
        observed_output_tokens, observed_output_count = _observed_sum(rows, "output_tokens")
        constraint_seconds = _sum_present(rows, "constraint_seconds")
        constraint_calls = _sum_present(rows, "constraint_calls")
        summary.update(
            input_tokens_total=_sum_present(rows, "input_tokens"),
            output_tokens_total=_sum_present(rows, "output_tokens"),
            input_tokens_observed_total=observed_input_tokens,
            input_token_observations=observed_input_count,
            output_tokens_observed_total=observed_output_tokens,
            output_token_observations=observed_output_count,
            decoder_steps_observed_total=_sum_present(rows, "decoder_steps_observed"),
            constraint_calls_total=constraint_calls,
            constraint_seconds_total=constraint_seconds,
            non_constraint_seconds_total=_sum_present(rows, "non_constraint_seconds"),
            constraint_seconds_per_decoder_step=(
                constraint_seconds / constraint_calls
                if constraint_seconds is not None and constraint_calls
                else None
            ),
            constraint_seconds_per_observed_output_token=(
                constraint_seconds / observed_output_tokens
                if constraint_seconds is not None and observed_output_tokens
                else None
            ),
            output_token_cap=token_cap,
            candidates_hitting_output_cap=(
                sum(
                    row.get("output_tokens") is not None
                    and row["output_tokens"] >= token_cap
                    for row in rows
                )
                if token_cap is not None
                else None
            ),
            parser_fallback_candidates=sum(
                bool(row.get("parser_fallback_to_unconstrained")) for row in rows
            ),
            parser_fail_closed_candidates=sum(
                bool(row.get("parser_fail_closed")) for row in rows
            ),
            java_online_stop_candidates=sum(
                bool(row.get("java_online_stop_triggered")) for row in rows
            ),
            java_complete_unit_truncation_candidates=sum(
                row.get("java_postprocess") == "complete_unit_truncation"
                for row in rows
            ),
            java_method_close_completion_candidates=sum(
                row.get("java_postprocess") == "method_close_class_completion"
                for row in rows
            ),
            generation_timeout_candidates=sum(
                bool(row.get("generation_timed_out")) for row in rows
            ),
            proposal_preserving_rejection=(
                method == "syncode_java_cfg_proposal_preserving_rejection"
            ),
            rejected_tokens_total=sum(
                len(row.get("rejected_tokens", [])) for row in rows
            ),
            candidates_with_rejection=sum(
                bool(row.get("rejected_tokens", [])) for row in rows
            ),
            constraint_support_expansions_total=sum(
                row.get("constraint_support_expansions", 0) for row in rows
            ),
            lm_seconds_total=_sum_present(rows, "lm_seconds"),
        )
    elif method.endswith("_compile_safe_portfolio"):
        summary.update(
            constrained_replacements=sum(
                row.get("selection") == "constrained" for row in rows
            ),
            ordinary_generation_seconds_total=_sum_present(
                rows, "ordinary_generation_seconds"
            ),
            constrained_generation_seconds_total=_sum_present(
                rows, "constrained_generation_seconds"
            ),
            compile_gate_seconds_total=_sum_present(rows, "compile_gate_seconds"),
            ordinary_standalone_compile_successes=sum(
                bool(row["ordinary_compile"]["success"]) for row in rows
            ),
            constrained_standalone_compile_successes_among_ordinary_failures=sum(
                bool(
                    row.get("constrained_compile")
                    and row["constrained_compile"]["success"]
                )
                for row in rows
            ),
            lm_generation_budget_multiplier=manifest.get(
                "lm_generation_budget_multiplier"
            ),
            selection_policy=manifest.get("selection_policy"),
        )
    elif method == "compiler_feedback_refinement":
        token_cap = run_args.get("max_tokens_per_call")
        initial_compile_successes = sum(
            bool(row["rounds"][0]["compile"]["success"]) for row in rows
        )
        final_compile_successes = sum(
            bool(row["rounds"][-1]["compile"]["success"]) for row in rows
        )
        summary.update(
            model_calls_total=sum(row["model_calls"] for row in rows),
            repair_calls_total=sum(row["repair_calls"] for row in rows),
            initial_compile_successes=initial_compile_successes,
            final_compile_successes=final_compile_successes,
            newly_compile_successful_candidates=(
                final_compile_successes - initial_compile_successes
            ),
            total_input_tokens=_sum_present(rows, "total_input_tokens"),
            total_output_tokens=_sum_present(rows, "total_output_tokens"),
            output_token_cap_per_call=token_cap,
            rounds_hitting_output_cap=(
                sum(
                    round_data.get("output_tokens", 0) >= token_cap
                    for row in rows
                    for round_data in row["rounds"]
                )
                if token_cap is not None
                else None
            ),
        )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize Java baseline trajectories.")
    parser.add_argument("--output_dir", type=Path, required=True)
    parser.add_argument("--json_out", type=Path)
    args = parser.parse_args()
    result = summarize(args.output_dir)
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(rendered + "\n")


if __name__ == "__main__":
    main()
