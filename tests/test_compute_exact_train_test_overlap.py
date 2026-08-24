import importlib.util
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "compute_exact_train_test_overlap.py"
)
SPEC = importlib.util.spec_from_file_location("exact_overlap", MODULE_PATH)
exact_overlap = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(exact_overlap)


def test_overlap_uses_complete_row_equality_and_test_order():
    train = [
        {"id": 1, "nested": {"left": 2, "right": 3}},
        {"id": 2, "tokens": [4, 5]},
    ]
    test = [
        {"id": 2, "tokens": [4, 5]},
        {"id": 1, "nested": {"right": 3, "left": 2}},
        {"id": 1, "nested": {"left": 2, "right": 4}},
    ]

    assert exact_overlap.overlap_indices(train, test) == [0, 1]
