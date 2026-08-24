import pytest

from score_sufu_no_write import compare_executor_output


def test_test_result_comparison_ignores_generated_declarations():
    expected = "gold_name : List -> Int\n0 : Int\n1 : Int\n"
    actual = "other_name : List -> Int\n0 : Int\n1 : Int\n"
    tests = "main (nil unit);\nmain (cons {1, (nil unit)});\n"
    assert actual != expected
    assert compare_executor_output(actual, expected, tests, test_results_only=True)


def test_test_result_comparison_rejects_wrong_result():
    expected = "gold_name : List -> Int\n0 : Int\n1 : Int\n"
    actual = "other_name : List -> Int\n0 : Int\n2 : Int\n"
    tests = "main (nil unit);\nmain (cons {1, (nil unit)});\n"
    assert not compare_executor_output(actual, expected, tests, test_results_only=True)


def test_test_result_comparison_requires_tests():
    with pytest.raises(ValueError):
        compare_executor_output("", "", "", test_results_only=True)
