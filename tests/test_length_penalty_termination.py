"""Regression tests for length-penalised completion-set termination."""

from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from beamsearch_coq import finishsetBm as CoqFinishSet
from beamsearch_sufu import finishsetBm as SufuFinishSet


def _completed_node(prob, length):
    return SimpleNamespace(prob=prob, state=[0] * length)


def _check_finish_set(finish_set_type):
    completed = finish_set_type(beamsize=1, length_penalty=0.1)
    # This completed sequence has normalised score -1 / 10**0.1.
    completed.add(_completed_node(-1.0, 10))
    assert completed.set[0].raw_prob == -1.0
    assert completed.set[0].normalized_score == completed.set[0].prob

    # A live node at length 10 has worse score now (-1.2 / 10**0.1), but it
    # could reach length 100 with no further loss and then beat the completed
    # sequence.  The old implementation incorrectly returned True here.
    assert not completed.isfinish(-1.2, curlen=10, max_len=100)

    # With no length penalty the raw log-probability is a valid upper bound.
    raw = finish_set_type(beamsize=1, length_penalty=0.0)
    raw.add(_completed_node(-1.0, 10))
    assert raw.isfinish(-1.2, curlen=10, max_len=100)


def test_coq_length_penalty_termination_uses_reachable_length_bound():
    _check_finish_set(CoqFinishSet)


def test_sufu_length_penalty_termination_uses_reachable_length_bound():
    _check_finish_set(SufuFinishSet)


class _RenderableNode(SimpleNamespace):
    def to_java(self):
        return "partial java"

    def to_str(self):
        return "partial sufu"


def _check_incomplete_nodes_are_not_finalized(finish_set_type):
    finished = finish_set_type(beamsize=1, length_penalty=0.1)
    finished.add(_RenderableNode(prob=-1.0, state=[0, 1], isfinish=False))
    finished.finalize()
    assert finished.final_set == []


def test_coq_finish_set_drops_incomplete_nodes():
    _check_incomplete_nodes_are_not_finalized(CoqFinishSet)


def test_sufu_finish_set_drops_incomplete_nodes():
    _check_incomplete_nodes_are_not_finalized(SufuFinishSet)


class _UnrenderableJavaNode(SimpleNamespace):
    def to_java(self):
        raise ValueError("invalid character literal")


def test_coq_finish_set_skips_unrenderable_candidate():
    finished = CoqFinishSet(beamsize=1, length_penalty=0.1)
    finished.add(
        _UnrenderableJavaNode(prob=-1.0, state=[0, 1], isfinish=True)
    )
    finished.finalize()
    assert finished.final_set == []
    assert finished.final_metadata == []
