"""Subset scoring must not share a temporary compiler directory."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from score_java_no_write import score_work_root as java_work_root
from score_sufu_no_write import score_work_root as sufu_work_root


def _check(factory):
    full = factory("task", "test", "generated", "all")
    subset = factory("task", "test", "generated", "indices=1,2")
    assert full != subset
    assert full == factory("task", "test", "generated", "all")


def test_java_subset_scoring_has_a_distinct_workdir():
    _check(java_work_root)


def test_sufu_subset_scoring_has_a_distinct_workdir():
    _check(sufu_work_root)
