import re

import pytest

import baselines.java_baselines.run_decoder_only_sufu as run_module
from baselines.java_baselines.run_decoder_only_sufu import _clean_response
from baselines.java_baselines.run_decoder_only_sufu import build_messages


def test_sufu_main_completion_boundary_is_explicit():
    generated = "main = \\xs: List. align (label xs);"
    match = re.search(r"(?m)^\s*main\s*=", generated)
    assert match and ";" in generated[match.end() :]


def test_clean_response_drops_copied_synthetic_prompt_after_target_code():
    response = r"""
main = first_or_zero;

TASK DESCRIPTION/PREFIX:
**Return the first integer in a list, or 0 for an empty list.**
Inductive List = nil Unit | cons {Int, List};
COMPLETE SUFU SOURCE:
Inductive List = nil Unit | cons {Int, List};
first_or_zero = fix (\f: List -> Int. \xs: List. 0);
main = first_or_zero;
TARGET SUFU TASK:
"""
    cleaned = _clean_response(response)
    assert cleaned == "main = first_or_zero;"


def test_clean_response_keeps_code_generated_after_target_marker():
    response = r"""
TASK DESCRIPTION/PREFIX:
example
TARGET SUFU TASK:
Inductive List = nil Unit | cons {Int, List};
main = first_or_zero;
"""
    cleaned = _clean_response(response)
    assert cleaned.startswith("Inductive List")
    assert "main = first_or_zero;" in cleaned


def test_clean_response_drops_demo_restart_after_prefix_completion():
    response = r"""
main = target;

Inductive List = nil Unit | cons {Int, List};
sum = fix (\f: List -> Int. \xs: List. 0);
"""
    assert _clean_response(response) == "main = target;"


def test_clean_response_drops_explanation_after_complete_main():
    response = r"""
Inductive List = nil Unit;
main = \xs: List. 0;

Okay, the program above computes the requested result.
"""
    assert _clean_response(response).endswith("main = \\xs: List. 0;")
    assert "Okay, the program" not in _clean_response(response)


def test_full_source_prompt_marks_target_completion_boundary():
    messages = build_messages(
        {
            "prompt": "Inductive List = nil Unit;",
            "code": "",
        },
        [
            {
                "prompt": "Inductive Example = ex Unit;",
                "code": "Inductive Example = ex Unit;\nmain = ex unit;",
            }
        ],
        "full_source",
        guidance_profile="high_information",
    )
    assert messages[-1]["content"].endswith("COMPLETE SUFU SOURCE:")


def test_full_source_prompt_distinguishes_demo_and_target_boundaries():
    messages = build_messages(
        {
            "prompt": "Inductive List = nil Unit;",
            "code": "",
        },
        [
            {
                "prompt": "Inductive Example = ex Unit;",
                "code": "Inductive Example = ex Unit;\nmain = ex unit;",
            }
        ],
        "full_source",
        guidance_profile="high_information",
    )
    content = messages[-1]["content"]
    assert content.count("EXAMPLE SUFU SOURCE:") == 1
    assert content.count("COMPLETE SUFU SOURCE:") == 1
    assert content.endswith("COMPLETE SUFU SOURCE:")


def test_sufu_rejects_debug_or_test_few_shot_rows():
    row = {"task_id": "leaked", "prompt": "p", "code": "c", "original_split": "test"}
    with pytest.raises(ValueError, match="test/valid/debug"):
        run_module._validate_few_shot_rows([row])
    debug_row = {"task_id": "debug", "prompt": "p", "code": "c", "type": "debug"}
    with pytest.raises(ValueError, match="test/valid/debug"):
        run_module._validate_few_shot_rows([debug_row])
