#!/usr/bin/env python3
"""Build a clearly labelled seen/unseen interpolation diagnostic task.

The task is evaluation-only.  It combines every frozen held-out row with an
equal-sized, deterministic IR-length-stratified sample from the source train
split.  The manifest keeps provenance for subgroup scoring; the combined
number must never be reported as a held-out benchmark result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pickle
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "Utils" / "data"
ARTIFACTS = ("rules.pkl", "rules.json", "tokenizer.pkl", "coq_tokenizer.pkl")


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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--seed", type=int, default=273567)
    parser.add_argument("--seen-rows", type=int, default=0)
    args = parser.parse_args()

    source = DATA / args.source
    target = DATA / args.target
    if target.exists():
        raise FileExistsError(f"refusing to overwrite {target}")

    train_proof = load_pickle(source / "train.pkl")
    test_proof = load_pickle(source / "test.pkl")
    train_plain = json.loads((source / "train_t5_plain_format.json").read_text())
    test_plain = json.loads((source / "test_t5_plain_format.json").read_text())
    train_ids = json.loads((source / "train_task_ids.json").read_text())
    test_ids = json.loads((source / "test_task_ids.json").read_text())
    if not (
        len(train_proof) == len(train_plain) == len(train_ids)
        and len(test_proof) == len(test_plain) == len(test_ids)
    ):
        raise RuntimeError("source proof/plain/task-ID counts differ")
    if set(train_ids) & set(test_ids):
        raise RuntimeError("source train/test task IDs overlap")

    seen_rows = args.seen_rows or len(test_ids)
    if seen_rows < 1 or seen_rows > len(train_ids):
        raise ValueError("seen row count is outside the source training population")
    length_order = sorted(
        range(len(train_proof)),
        key=lambda index: (len(train_proof[index]["rulelist"]), train_ids[index]),
    )
    quartile = [0] * len(train_ids)
    for rank, index in enumerate(length_order):
        quartile[index] = min(4, 4 * rank // len(length_order) + 1)

    selected = []
    base, remainder = divmod(seen_rows, 4)
    for value in range(1, 5):
        count = base + (1 if value <= remainder else 0)
        candidates = [index for index, item in enumerate(quartile) if item == value]
        candidates.sort(
            key=lambda index: (
                hashlib.sha256(
                    f"{args.seed}:{source.name}:{train_ids[index]}".encode()
                ).hexdigest(),
                train_ids[index],
            )
        )
        selected.extend(candidates[:count])
    if len(selected) != seen_rows or len(selected) != len(set(selected)):
        raise RuntimeError("deterministic seen selection has invalid cardinality")

    proof = [train_proof[index] for index in selected] + list(test_proof)
    plain = [dict(train_plain[index], type="test", split="test") for index in selected]
    plain += [dict(row, type="test", split="test") for row in test_plain]
    provenance = [
        {
            "evaluation_index": output_index,
            "source_split": "train_seen",
            "source_index": index,
            "task_id": train_ids[index],
            "ir_length_quartile": quartile[index],
        }
        for output_index, index in enumerate(selected)
    ]
    provenance += [
        {
            "evaluation_index": seen_rows + index,
            "source_split": "heldout_test",
            "source_index": index,
            "task_id": task_id,
        }
        for index, task_id in enumerate(test_ids)
    ]

    target.mkdir(parents=True)
    try:
        for artifact in ARTIFACTS:
            shutil.copy2(source / artifact, target / artifact)
        for split, rows in (("train", []), ("valid", []), ("test", proof)):
            dump_pickle(rows, target / f"{split}.pkl")
            (target / f"{split}.json").write_text(
                json.dumps(rows, indent=2, ensure_ascii=False) + "\n"
            )
        (target / "train_t5_plain_format.json").write_text("[]\n")
        (target / "valid_t5_plain_format.json").write_text("[]\n")
        (target / "test_t5_plain_format.json").write_text(
            json.dumps(plain, indent=2, ensure_ascii=False) + "\n"
        )
        (target / "test_mbjp_t5.json").write_text(
            json.dumps(plain, indent=2, ensure_ascii=False) + "\n"
        )
        config = json.loads((source / "config.json").read_text())
        config.update(
            {
                "validation": False,
                "evaluation_only": True,
                "train_rows": 0,
                "valid_rows": 0,
                "test_rows": len(proof),
                "data_revision": "seen-unseen-interpolation-diagnostic-v1",
            }
        )
        (target / "config.json").write_text(json.dumps(config, indent=2) + "\n")
        manifest = {
            "task": args.target,
            "source_task": args.source,
            "role": "debug/interpolation diagnostic only; not a held-out benchmark",
            "seed": args.seed,
            "selection_uses_model_outputs": False,
            "selection_uses_execution_outcomes": False,
            "seen_train_rows": seen_rows,
            "heldout_test_rows": len(test_ids),
            "total_rows": len(proof),
            "validation_rows": 0,
            "ordering": "all deterministic seen rows, then all frozen held-out rows",
            "rows": provenance,
            "test_pickle_sha256": sha256(target / "test.pkl"),
        }
        (target / "seen_unseen_diagnostic_manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
        )
        print(json.dumps(manifest, indent=2, ensure_ascii=False))
    except Exception:
        shutil.rmtree(target)
        raise


if __name__ == "__main__":
    main()
