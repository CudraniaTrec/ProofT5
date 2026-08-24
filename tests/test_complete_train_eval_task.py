"""Unit checks for complete-train/frozen-test task construction helpers."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.build_complete_train_eval_task import max_lengths, strip_additional_row_markers


def test_additional_training_markers_are_not_carried_into_complete_train_rows():
    row = {
        "rulelist": [1, 2, 3, 4],
        "prefix": [2],
        "nl": [7, 8],
        "debug_overlap": True,
        "debug_source_index": 4,
        "debug_source_split": "test",
        "split": "additional",
        "task_id": 9,
    }
    cleaned = strip_additional_row_markers(row)
    assert cleaned["task_id"] == 9
    assert all(not key.startswith("debug_") for key in cleaned)
    assert "split" not in cleaned


def test_lengths_cover_complete_train_and_benchmark_test_rows():
    rows = [
        {"rulelist": [1, 2, 3, 4], "prefix": [2], "nl": [7, 8]},
        {"rulelist": [1, 2, 3, 4, 5, 6], "prefix": [2, 3], "nl": [7, 8, 9]},
    ]
    assert max_lengths(rows) == {"CodeLen": 4, "max_code_len": 2, "NlLen": 3}
