"""Regression tests for deferred final-program Coq validation."""

from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from beamsearch_coq import BeamSearch


def _beam(final_only):
    beam = object.__new__(BeamSearch)
    beam.final_only_coq_check = final_only
    return beam


def test_final_only_mode_skips_unfinished_prefix_check():
    assert not _beam(True)._requires_coq_check(SimpleNamespace(isfinish=False))


def test_final_only_mode_still_checks_complete_program():
    assert _beam(True)._requires_coq_check(SimpleNamespace(isfinish=True))


def test_default_mode_checks_prefix_and_complete_program():
    beam = _beam(False)
    assert beam._requires_coq_check(SimpleNamespace(isfinish=False))
    assert beam._requires_coq_check(SimpleNamespace(isfinish=True))
