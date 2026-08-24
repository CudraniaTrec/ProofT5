import importlib.util
import json
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "audit_sufu_generated_candidates.py"
)
SPEC = importlib.util.spec_from_file_location("audit_sufu_outputs", MODULE_PATH)
audit_sufu_outputs = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit_sufu_outputs)


def write_candidate(output_dir, problem_id, candidate_id, code, score=-1.0):
    (output_dir / f"{problem_id}_{candidate_id}.txt").write_text(code)
    (output_dir / f"{problem_id}_beam_scores.json").write_text(
        json.dumps(
            {
                "problem_id": problem_id,
                "beam_size": 1,
                "candidates": [
                    {
                        "raw_log_probability": score,
                        "normalized_score": score,
                        "scoring_length": 2,
                        "length_penalty": 0.0,
                    }
                ],
            }
        )
    )


def test_surface_and_beam_score_audit_accepts_valid_output(tmp_path):
    write_candidate(tmp_path, 0, 0, "x = 1;\nmain = x;")
    report, passed = audit_sufu_outputs.audit_output_dir(tmp_path, 1, 1, True)
    assert passed
    assert report["candidate_files"] == 1


def test_surface_audit_rejects_unbound_output(tmp_path):
    write_candidate(tmp_path, 0, 0, "main = missing;")
    report, passed = audit_sufu_outputs.audit_output_dir(tmp_path, 1, 1, True)
    assert not passed
    assert report["invalid_surface_candidates"][0]["problem_id"] == 0


def test_selected_problem_audit_does_not_require_unselected_outputs(tmp_path):
    write_candidate(tmp_path, 2, 0, "main = 1;")
    report, passed = audit_sufu_outputs.audit_output_dir(
        tmp_path, 3, 1, True, [2]
    )
    assert passed
    assert report["problem_ids"] == [2]
