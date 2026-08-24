import json
from pathlib import Path

import pytest

from scripts.merge_candidate_output_shards import merge


def write_problem(root: Path, problem_id: int, candidates: int, text: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for rank in range(candidates):
        (root / f"{problem_id}_{rank}.txt").write_text(f"{text}-{rank}")
    (root / f"{problem_id}_beam_scores.json").write_text(
        json.dumps({"problem_id": problem_id})
    )


def test_merge_disjoint_shards_and_manifest(tmp_path: Path) -> None:
    first, second, output = tmp_path / "first", tmp_path / "second", tmp_path / "out"
    write_problem(first, 0, 2, "zero")
    write_problem(second, 1, 2, "one")

    manifest = merge([first, second], output, expected_size=2, candidates=2)

    assert manifest["copied_file_count"] == 6
    assert (output / "0_0.txt").read_text() == "zero-0"
    assert (output / "1_1.txt").read_text() == "one-1"
    assert json.loads((output / "merge_manifest.json").read_text())["expected_problem_ids"] == [0, 1]


def test_merge_rejects_missing_and_conflicting_files(tmp_path: Path) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    write_problem(first, 0, 1, "original")

    with pytest.raises(ValueError, match="missing"):
        merge([first], tmp_path / "missing-out", expected_size=2, candidates=1)

    write_problem(second, 0, 1, "different")
    with pytest.raises(ValueError, match="conflicting duplicate"):
        merge([first, second], tmp_path / "conflict-out", expected_size=1, candidates=1)


def test_sparse_merge_manifests_beam_exhaustion_but_still_requires_metadata(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    write_problem(source, 0, 2, "zero")
    (source / "0_1.txt").unlink()

    output = tmp_path / "sparse-out"
    manifest = merge(
        [source],
        output,
        expected_size=1,
        candidates=2,
        allow_missing_candidates=True,
    )

    assert manifest["schema_version"] == 2
    assert manifest["allow_missing_candidates"] is True
    assert manifest["missing_candidate_files"] == ["0_1.txt"]
    assert manifest["missing_candidate_count"] == 1
    assert manifest["missing_beam_metadata_files"] == []
    assert manifest["expected_file_count"] == 3
    assert manifest["copied_file_count"] == 2
    assert not (output / "0_1.txt").exists()

    (source / "0_beam_scores.json").unlink()
    with pytest.raises(ValueError, match="beam_scores"):
        merge(
            [source],
            tmp_path / "missing-metadata-out",
            expected_size=1,
            candidates=2,
            allow_missing_candidates=True,
        )
