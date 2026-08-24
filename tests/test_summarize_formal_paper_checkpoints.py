import importlib.util
import json
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "summarize_formal_paper_checkpoints.py"
)
SPEC = importlib.util.spec_from_file_location("formal_summary", MODULE_PATH)
formal_summary = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(formal_summary)


def write_score(path, *, model_type, problems, pass1, pass10, fsp, cer):
    top1_count = round(pass1 * problems)
    pass10_count = round(pass10 * problems)
    path.write_text(
        json.dumps(
            {
                "model_type": model_type,
                "model_checkpoint_path": f"/models/{model_type}.ckpt",
                "model_checkpoint_sha256": model_type * 8,
                "problems": problems,
                "pass_at_k": 10,
                "pass1": pass1,
                "pass10": pass10,
                "average_first_success_position": fsp,
                "compile_error_rate": cer,
                "top1_solved": list(range(top1_count)),
                "solved": list(range(pass10_count)),
                "missing": 0,
                "timeouts": 0,
                "compile_errors": 0,
                "total_tested": problems * 10,
            }
        )
    )


def test_score_row_computes_paper_distance_and_solved_counts(tmp_path):
    score_path = tmp_path / "epoch3.json"
    write_score(
        score_path,
        model_type="epoch3",
        problems=58,
        pass1=0.431,
        pass10=0.5,
        fsp=5.03,
        cer=0.0,
    )

    row = formal_summary.score_row(score_path, "sufu", "full")

    assert row["checkpoint"] == "epoch3"
    assert row["pass1_solved"] == 25
    assert row["pass10_solved"] == 29
    assert row["paper_l2_distance"] == 0.0


def test_full_scope_requires_frozen_test_size(tmp_path):
    score_path = tmp_path / "wrong-size.json"
    write_score(
        score_path,
        model_type="epoch0",
        problems=57,
        pass1=0.0,
        pass10=0.0,
        fsp=10.0,
        cer=0.0,
    )

    try:
        formal_summary.score_row(score_path, "sufu", "full")
    except ValueError as error:
        assert "expected 58" in str(error)
    else:
        raise AssertionError("wrong-sized full score should be rejected")


def test_markdown_warns_about_java_paper_denominator():
    summary = {
        "branch": "java",
        "paper_target": formal_summary.PAPER_TARGETS["java"],
        "closest_full_checkpoint": "epoch2",
        "rows": [],
    }

    markdown = formal_summary.render_markdown(summary)

    assert "23.19% is not attainable on 67 problems" in markdown
    assert "Non-overlap rows" in markdown
