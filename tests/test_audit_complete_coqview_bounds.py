import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path("scripts/audit_complete_coqview_bounds.py")
SPEC = importlib.util.spec_from_file_location("audit_complete_coqview_bounds", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def config():
    return {
        "NlLen": 4,
        "max_code_len": 3,
        "max_coqview_len": 2,
        "cut_prefix": True,
    }


def row():
    return {
        "nl": [9, 8],
        "rulelist": [0, 1, 2, 3, 4, 5],
        "prefix": [1, 2],
        "coqview": [[7], [7, 8], [8]],
    }


def test_split_audit_accepts_exact_cut_prefix_bounds():
    result = MODULE.audit_split([row()], config(), "train", 16, 16)
    assert result["rows"] == 1
    assert result["active_suffix_targets"] == 2
    assert result["maxima"]["decoder_positions"] == 3
    assert result["unexpected_truncation_risk"] is False


def test_split_audit_rejects_suffix_that_collator_would_truncate():
    bad = row()
    bad["rulelist"] = [0, 1, 2, 3, 4, 5, 6, 7]
    bad["coqview"].extend([[7], [8]])
    with pytest.raises(ValueError, match="suffix 4 > max_code_len 3"):
        MODULE.audit_split([bad], config(), "train", 16, 16)


def test_split_audit_rejects_context_step_misalignment():
    bad = row()
    bad["coqview"] = bad["coqview"][:-1]
    with pytest.raises(ValueError, match="cut contexts"):
        MODULE.audit_split([bad], config(), "test", 16, 16)
