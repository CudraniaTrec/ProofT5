"""Checks for proof/plain-aligned evaluation subset construction."""

import json
import pickle

from scripts.build_evaluation_subset_task import ARTIFACTS, build_task


def _dump_pickle(path, value):
    with path.open("wb") as handle:
        pickle.dump(value, handle)


def test_parallel_plain_rows_follow_the_frozen_proof_indices(tmp_path):
    data_root = tmp_path / "data"
    source = data_root / "source"
    source.mkdir(parents=True)
    proof_rows = [
        {"task_id": "proof-a", "benchmark": "mbjp", "value": 1},
        {"task_id": "proof-b", "benchmark": "humaneval", "value": 2},
        {"task_id": "proof-c", "benchmark": "mbjp", "value": 3},
    ]
    _dump_pickle(source / "train.pkl", proof_rows)
    (source / "train.json").write_text(json.dumps(proof_rows))
    (source / "config.json").write_text(json.dumps({"validation": True}))
    for name in ARTIFACTS:
        (source / name).write_bytes(name.encode())

    plain_path = tmp_path / "plain.json"
    plain_rows = [
        {"task_id": "plain-a", "benchmark": "mbjp", "type": "train"},
        {"task_id": "plain-b", "benchmark": "humaneval", "type": "train"},
        {"task_id": "plain-c", "benchmark": "mbjp", "type": "train"},
    ]
    plain_path.write_text(json.dumps(plain_rows))

    manifest = build_task(
        data_root,
        "source",
        "train",
        "mbjp",
        "target",
        parallel_plain_json=plain_path,
    )

    target = data_root / "target"
    selected_plain = json.loads((target / "test_t5_plain_format.json").read_text())
    assert manifest["source_indices"] == [0, 2]
    assert [row["task_id"] for row in selected_plain] == ["plain-a", "plain-c"]
    assert all(row["type"] == "test" and row["split"] == "test" for row in selected_plain)
    assert pickle.load((target / "test.pkl").open("rb")) == [proof_rows[0], proof_rows[2]]
