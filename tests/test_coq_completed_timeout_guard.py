"""Regression test for completed candidates whose Coq check times out."""

from pathlib import Path
import sys
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from beamsearch_coq import BeamSearch


def test_coq_timeout_is_deferred_only_for_unfinished_prefixes():
    unfinished = SimpleNamespace(isfinish=False)
    completed = SimpleNamespace(isfinish=True)

    assert BeamSearch._coq_status_allows_candidate(unfinished, None)
    assert not BeamSearch._coq_status_allows_candidate(completed, None)
    assert BeamSearch._coq_status_allows_candidate(completed, True)
    assert not BeamSearch._coq_status_allows_candidate(unfinished, False)


if __name__ == "__main__":
    test_coq_timeout_is_deferred_only_for_unfinished_prefixes()
