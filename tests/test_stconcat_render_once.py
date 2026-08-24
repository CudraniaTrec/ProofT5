"""Regression tests for linear-time StConcat rendering."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from coq_model.program_model import StConcat, Statement


class CountingStatement(Statement):
    terms_need = []

    def __init__(self, java, code):
        self.java = java
        self.code = code
        self.java_calls = 0
        self.code_calls = 0
        self.complete = True

    def to_java(self, context={}):
        self.java_calls += 1
        return self.java

    def to_code(self):
        self.code_calls += 1
        return self.code


def test_to_java_renders_each_child_once():
    left = CountingStatement("left", "left")
    right = CountingStatement("right", "right")
    assert StConcat(left, right).to_java({}) == "left\nright"
    assert (left.java_calls, right.java_calls) == (1, 1)


def test_to_java_empty_right_and_comma_context_preserve_output():
    left = CountingStatement("left", "left")
    empty = CountingStatement("", "skip")
    assert StConcat(left, empty).to_java({"comma": True}) == "left"
    assert (left.java_calls, empty.java_calls) == (1, 1)

    left = CountingStatement("left", "left")
    right = CountingStatement("right", "right")
    assert StConcat(left, right).to_java({"comma": True}) == "left, right"


def test_to_code_renders_each_child_once():
    left = CountingStatement("left", "left")
    right = CountingStatement("right", "right")
    assert StConcat(left, right).to_code() == "left;\nright"
    assert (left.code_calls, right.code_calls) == (1, 1)
