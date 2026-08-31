from baselines.java_baselines.run_decoder_only_sufu import _clean_response


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
