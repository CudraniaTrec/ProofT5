#!/usr/bin/env python3
"""Regression checks for auditable complete-training CoqView task building."""

import importlib.util
import json
import pickle
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "complete_coqview_builder", ROOT / "scripts" / "build_complete_coqview_task.py"
)
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


def dump(value, path):
    with path.open("wb") as handle:
        pickle.dump(value, handle)


def row(java_code, coqview=None):
    value = {
        "rulelist": [0, 5, 6, 1],
        "prefix": [5],
        "tokens": [10, 11],
        "nl": [20],
        "test": "assert true;",
        "java_code": java_code,
    }
    if coqview is not None:
        value["coqview"] = coqview
        value["coqview_raw"] = "Context: empty"
    return value


def make_task(path, rows, config):
    path.mkdir()
    for split, split_rows in rows.items():
        dump(split_rows, path / f"{split}.pkl")
    dump(list(range(32)), path / "tokenizer.pkl")
    dump(list(range(32)), path / "coq_tokenizer.pkl")
    dump({"rule": 1}, path / "rules.pkl")
    (path / "rules.json").write_text('{"rule": 1}\n')
    (path / "config.json").write_text(json.dumps(config) + "\n")


with tempfile.TemporaryDirectory() as temp:
    temp = Path(temp)
    source = temp / "source"
    reference = temp / "reference"
    template = temp / "template"
    target = temp / "target"
    source_row = row("new formatting")
    donor_row = row("historical formatting", coqview=[[3, 4]])
    make_task(
        source,
        {"train": [source_row], "valid": [], "test": [source_row]},
        {"data_revision": "source", "CodeLen": 99, "max_code_len": 88, "NlLen": 77},
    )
    make_task(reference, {"train": [donor_row], "valid": [], "test": [donor_row]}, {"enable_coqview": True})
    make_task(
        template,
        {"train": [], "valid": [], "test": []},
        {"enable_coqview": True, "CodeLen": 4, "max_code_len": 3, "NlLen": 2},
    )
    parent = temp / "parent.ckpt"
    parent.write_bytes(b"checkpoint")

    artifacts = builder.check_artifacts(source, reference, template)
    donors, plan, missing = builder.build_plan(source, reference, "java", 32)
    assert plan == {
        "train": {"rows": 1, "reuse": 1, "convert": 0},
        "valid": {"rows": 0, "reuse": 0, "convert": 0},
        "test": {"rows": 1, "reuse": 1, "convert": 0},
    }
    rows = builder.build_rows(source, donors, missing, "java", list(range(32)), {}, temp / "cache", 1, 1)
    assert rows["train"][0]["java_code"] == "new formatting"
    assert rows["train"][0]["coqview"] == [[3, 4]]
    builder.write_task(
        target, source, reference, template, "target", "parent", parent,
        rows, plan, artifacts, "java",
    )
    manifest = json.loads((target / "coqview_build_manifest.json").read_text())
    assert manifest["reference_coqview_task"] == "reference"
    assert manifest["max_coqview_len"] == 2
    config = json.loads((target / "config.json").read_text())
    assert {key: config[key] for key in ("CodeLen", "max_code_len", "NlLen")} == {
        "CodeLen": 99,
        "max_code_len": 88,
        "NlLen": 77,
    }
    assert len(pickle.load((target / "valid.pkl").open("rb"))) == 0
    assert json.loads((target / "train.json").read_text()) == pickle.load(
        (target / "train.pkl").open("rb")
    )

print("complete CoqView task builder regression tests passed")


with tempfile.TemporaryDirectory() as temp:
    temp = Path(temp)
    source = temp / "source"
    reference = temp / "reference"
    source_row = row("new prompt formatting")
    source_row["nl"] = [21]
    donor_row = row("old prompt formatting", coqview=[[3, 4]])
    make_task(source, {"train": [source_row], "valid": [], "test": []}, {})
    make_task(reference, {"train": [donor_row], "valid": [], "test": []}, {})
    _, strict_plan, _ = builder.build_plan(source, [reference], "java", 32)
    assert strict_plan["train"] == {"rows": 1, "reuse": 0, "convert": 1}
    fields = ("rulelist", "prefix", "tokens")
    donors, relaxed_plan, missing = builder.build_plan(
        source, [reference], "java", 32, fields
    )
    assert relaxed_plan["train"] == {"rows": 1, "reuse": 1, "convert": 0}
    rows = builder.build_rows(
        source, donors, missing, "java", list(range(32)), {}, temp / "cache", 1, 1,
        signature_fields=fields,
    )
    assert rows["train"][0]["nl"] == [21]
    assert rows["train"][0]["coqview"] == [[3, 4]]

print("CoqView nl-only donor regression tests passed")
