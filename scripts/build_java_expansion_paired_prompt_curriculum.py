#!/usr/bin/env python3
"""Pair adapted v8 expansion prompts with their original v6 prompts.

The source task supplies the replay order and targets.  MBJP rows are retained
once.  Every HumanEval/GFG occurrence is retained with its v8 prompt and paired
with a second row whose only change is the original v6 ``prompt``/``nl``.  The
paired curriculum is training-only and never copies a held-out row.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import pickle
import shutil
import tempfile
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "Utils" / "data"
ARTIFACTS = ("rules.pkl", "rules.json", "tokenizer.pkl", "coq_tokenizer.pkl")
TARGET_FIELDS = ("rulelist", "java_code", "test", "tokens", "prefix")
SOURCE_TO_DONOR = {
    "humaneval_java": "java_humaneval_mbjp_exact_coverage_split80_20_t5gemma2_20260819_v6",
    "transcoder_gfg": "java_transcoder_gfg_mbjp_exact_coverage_split80_20_t5gemma2_20260819_v6",
}


def load_pickle(path: Path):
    with path.open("rb") as handle:
        return pickle.load(handle)


def dump_pickle(value, path: Path) -> None:
    with path.open("wb") as handle:
        pickle.dump(value, handle, protocol=pickle.HIGHEST_PROTOCOL)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def donor_maps(task: str) -> tuple[dict[str, dict], dict[str, dict]]:
    directory = DATA / task
    ids = json.loads((directory / "train_task_ids.json").read_text())
    proofs = load_pickle(directory / "train.pkl")
    plains = json.loads((directory / "train_t5_plain_format.json").read_text())
    if len(ids) != len(proofs) or len(ids) != len(plains):
        raise RuntimeError(f"{task}: donor proof/plain/ID counts differ")
    if ids != [row["task_id"] for row in plains]:
        raise RuntimeError(f"{task}: donor task-ID order differs")
    return dict(zip(ids, proofs)), dict(zip(ids, plains))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-task", required=True)
    parser.add_argument("--target-task", required=True)
    parser.add_argument("--parent-task", required=True)
    args = parser.parse_args()

    source = DATA / args.source_task
    target = DATA / args.target_task
    parent = ROOT / "Utils" / "models" / f"Model{args.parent_task}" / "last_model.ckpt"
    if target.exists():
        raise FileExistsError(f"refusing to overwrite {target}")
    if not parent.is_file():
        raise FileNotFoundError(parent)
    source_proof = load_pickle(source / "train.pkl")
    source_plain = json.loads((source / "train_t5_plain_format.json").read_text())
    ledger = [
        json.loads(line)
        for line in (source / "balanced_replay_rows.jsonl").read_text().splitlines()
        if line
    ]
    if not (len(source_proof) == len(source_plain) == len(ledger)):
        raise RuntimeError("source proof/plain/replay ledger counts differ")

    donors = {name: donor_maps(task) for name, task in SOURCE_TO_DONOR.items()}
    proof_train = []
    plain_train = []
    output_ledger = []
    source_counts = Counter()
    paired_counts = Counter()
    for index, (proof, plain, provenance) in enumerate(
        zip(source_proof, source_plain, ledger)
    ):
        source_name = provenance["source"]
        task_id = provenance.get("source_task_id") or plain.get("task_id")
        proof_train.append(copy.deepcopy(proof))
        plain_train.append(copy.deepcopy(plain))
        output_ledger.append(
            {
                "materialized_index": len(output_ledger),
                "source_materialized_index": index,
                "source": source_name,
                "source_task_id": task_id,
                "prompt_variant": "semantic_signature_v8",
            }
        )
        source_counts[source_name] += 1
        if source_name == "mbjp":
            continue
        if source_name not in donors:
            raise RuntimeError(f"unknown expansion source: {source_name}")
        donor_proof, donor_plain = donors[source_name]
        if task_id not in donor_proof or task_id not in donor_plain:
            raise RuntimeError(f"missing v6 prompt donor: {source_name} {task_id}")
        for field in TARGET_FIELDS:
            if proof[field] != donor_proof[task_id][field]:
                raise RuntimeError(
                    f"v6/v8 target mismatch for {source_name} {task_id}: {field}"
                )
        proof_variant = copy.deepcopy(proof)
        proof_variant["nl"] = copy.deepcopy(donor_proof[task_id]["nl"])
        plain_variant = copy.deepcopy(plain)
        plain_variant["prompt"] = donor_plain[task_id]["prompt"]
        plain_variant["task_id"] = f"{task_id}/original_v6_prompt"
        proof_train.append(proof_variant)
        plain_train.append(plain_variant)
        output_ledger.append(
            {
                "materialized_index": len(output_ledger),
                "source_materialized_index": index,
                "source": source_name,
                "source_task_id": task_id,
                "prompt_variant": "original_v6",
            }
        )
        paired_counts[source_name] += 1

    expected = source_counts["mbjp"] + 2 * (
        source_counts["humaneval_java"] + source_counts["transcoder_gfg"]
    )
    if len(proof_train) != expected or len(plain_train) != expected:
        raise RuntimeError("paired curriculum materialization count is inconsistent")
    if any(row.get("type") not in {None, "train"} for row in plain_train):
        raise RuntimeError("non-training plain row entered the paired curriculum")
    for row in plain_train:
        row["type"] = "train"

    with tempfile.TemporaryDirectory(prefix=f".{args.target_task}.building-", dir=DATA) as tmp:
        out = Path(tmp)
        for name in ARTIFACTS:
            shutil.copy2(source / name, out / name)
        for split, rows in (("train", proof_train), ("valid", []), ("test", [])):
            dump_pickle(rows, out / f"{split}.pkl")
            (out / f"{split}.json").write_text(
                json.dumps(rows, indent=2, ensure_ascii=False) + "\n"
            )
        (out / "train_t5_plain_format.json").write_text(
            json.dumps(plain_train, indent=2, ensure_ascii=False) + "\n"
        )
        (out / "valid_t5_plain_format.json").write_text("[]\n")
        (out / "test_t5_plain_format.json").write_text("[]\n")
        config = json.loads((source / "config.json").read_text())
        config.update(
            {
                "pretrain_name": args.parent_task,
                "pretrain_model_type": "last",
                "strict_model_loading": True,
                "validation": False,
                "evaluation_only": False,
                "train_rows": len(proof_train),
                "valid_rows": 0,
                "test_rows": 0,
                "data_revision": (
                    "java-expansion-v8-coverage-neighbor-complex-signature-"
                    "paired-v6-v8-prompts-no-valid-no-test-v1"
                ),
            }
        )
        (out / "config.json").write_text(json.dumps(config, indent=2) + "\n")
        (out / "paired_prompt_rows.jsonl").write_text(
            "".join(json.dumps(row, sort_keys=True) + "\n" for row in output_ledger)
        )
        manifest = {
            "task": args.target_task,
            "source_task": args.source_task,
            "parent_task": args.parent_task,
            "parent_checkpoint_sha256": sha256(parent),
            "source_effective_rows": len(source_proof),
            "effective_train_rows": len(proof_train),
            "validation_rows": 0,
            "test_rows": 0,
            "source_occurrences": dict(source_counts),
            "paired_original_v6_prompt_occurrences": dict(paired_counts),
            "policy": (
                "retain MBJP once; pair every v8 HumanEval/GFG occurrence with the same "
                "target/test and its original v6 prompt/nl"
            ),
            "target_fields_verified_equal": list(TARGET_FIELDS),
            "selection_uses_model_outputs": False,
            "selection_uses_test_outcomes": False,
            "coverage_replay_uses_frozen_test_descriptions": True,
            "heldout_rows_copied": 0,
            "artifact_sha256": {
                name: sha256(out / name)
                for name in ("train.pkl", "valid.pkl", "test.pkl", "config.json")
            },
        }
        (out / "paired_prompt_manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n"
        )
        os.replace(out, target)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
