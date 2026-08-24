#!/usr/bin/env python3
"""Freeze an eight-row training-only probe for one expansion benchmark.

The probe contains two deterministic examples from each source-local IR-length
quartile.  It is exposed through the evaluator's test split only because the
evaluation code has no separate probe split; no held-out row or model output is
used in its construction.
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
    parser.add_argument("--rows-per-quartile", type=int, default=2)
    args = parser.parse_args()
    if args.rows_per_quartile < 1:
        parser.error("--rows-per-quartile must be positive")

    source = DATA / args.source
    target = DATA / args.target
    if target.exists():
        raise FileExistsError(f"refusing to overwrite {target}")

    proofs = load_pickle(source / "train.pkl")
    plains = json.loads((source / "train_t5_plain_format.json").read_text())
    task_ids = json.loads((source / "train_task_ids.json").read_text())
    if not (len(proofs) == len(plains) == len(task_ids)):
        raise RuntimeError("source proof/plain/task-ID lengths differ")

    length_order = sorted(
        range(len(proofs)),
        key=lambda index: (len(proofs[index]["rulelist"]), task_ids[index]),
    )
    quartiles = [0] * len(proofs)
    for rank, index in enumerate(length_order):
        quartiles[index] = min(4, 4 * rank // len(length_order) + 1)

    selected = []
    for quartile in range(1, 5):
        candidates = [index for index, value in enumerate(quartiles) if value == quartile]
        ranked = sorted(
            candidates,
            key=lambda index: (
                hashlib.sha256(
                    f"{args.seed}:{source.name}:{task_ids[index]}".encode()
                ).hexdigest(),
                task_ids[index],
            ),
        )
        if len(ranked) < args.rows_per_quartile:
            raise RuntimeError(f"quartile {quartile} has only {len(ranked)} rows")
        selected.extend((index, quartile) for index in ranked[: args.rows_per_quartile])

    selected_proofs = [proofs[index] for index, _ in selected]
    selected_plains = [dict(plains[index], type="test", split="test") for index, _ in selected]

    target.mkdir(parents=True)
    try:
        for artifact in ARTIFACTS:
            shutil.copy2(source / artifact, target / artifact)
        for split, rows in (("train", []), ("valid", []), ("test", selected_proofs)):
            dump_pickle(rows, target / f"{split}.pkl")
            (target / f"{split}.json").write_text(
                json.dumps(rows, indent=2, ensure_ascii=False) + "\n"
            )
        for name in ("test_mbjp_t5.json", "test_t5_plain_format.json"):
            (target / name).write_text(
                json.dumps(selected_plains, indent=2, ensure_ascii=False) + "\n"
            )
        (target / "train_t5_plain_format.json").write_text("[]\n")
        (target / "valid_t5_plain_format.json").write_text("[]\n")

        config = json.loads((source / "config.json").read_text())
        config.update(
            {
                "validation": False,
                "evaluation_only": True,
                "train_rows": 0,
                "valid_rows": 0,
                "test_rows": len(selected),
                "data_revision": "fixed-pre-evaluation-single-source-ir-quartile-training-probe-v1",
            }
        )
        (target / "config.json").write_text(json.dumps(config, indent=2) + "\n")
        manifest = {
            "task": args.target,
            "role": "training diagnostic only; not validation",
            "source_task": args.source,
            "seed": args.seed,
            "selection_uses_model_outputs": False,
            "selection_uses_heldout_rows": False,
            "selection_policy": (
                f"{args.rows_per_quartile} deterministic SHA-ranked training rows "
                "per source-local IR-length quartile"
            ),
            "rows": [
                {
                    "task_id": task_ids[index],
                    "ir_quartile": quartile,
                    "ir_length": len(proofs[index]["rulelist"]),
                }
                for index, quartile in selected
            ],
            "train_rows": 0,
            "validation_rows": 0,
            "probe_rows_exposed_as_test_for_evaluator": len(selected),
            "proof_test_pickle_sha256": sha256(target / "test.pkl"),
            "plain_test_json_sha256": sha256(target / "test_mbjp_t5.json"),
        }
        (target / "train_probe_manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
        )
        print(json.dumps(manifest, indent=2, ensure_ascii=False))
    except Exception:
        shutil.rmtree(target)
        raise


if __name__ == "__main__":
    main()
