#!/usr/bin/env python3
"""Extract one frozen expansion source from an audited replay curriculum.

This is the expansion-only counterpart to the benchmark-pair curriculum.  It
preserves proof/plain/replay alignment and multiplicity and creates no
validation or test rows.
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
    parser.add_argument("--source-task", required=True)
    parser.add_argument(
        "--expansion", choices=("humaneval_java", "transcoder_gfg"), required=True
    )
    parser.add_argument("--target-task", required=True)
    args = parser.parse_args()

    source = DATA / args.source_task
    target = DATA / args.target_task
    if target.exists():
        raise FileExistsError(f"refusing to overwrite {target}")
    proof = load_pickle(source / "train.pkl")
    plain = json.loads((source / "train_t5_plain_format.json").read_text())
    replay = [
        json.loads(line)
        for line in (source / "balanced_replay_rows.jsonl").read_text().splitlines()
        if line.strip()
    ]
    if not (len(proof) == len(plain) == len(replay)):
        raise RuntimeError("source proof/plain/replay lengths differ")
    indices = [i for i, row in enumerate(replay) if row["source"] == args.expansion]
    if len(indices) != 541:
        raise RuntimeError(f"expected 541 frozen occurrences, got {len(indices)}")
    selected_proof = [proof[i] for i in indices]
    selected_plain = [plain[i] for i in indices]
    selected_replay = []
    for new_index, old_index in enumerate(indices):
        row = dict(replay[old_index])
        row["source_materialized_index"] = row["materialized_index"]
        row["materialized_index"] = new_index
        selected_replay.append(row)

    target.mkdir(parents=True)
    try:
        dump_pickle(selected_proof, target / "train.pkl")
        dump_pickle([], target / "valid.pkl")
        dump_pickle([], target / "test.pkl")
        for split, rows in (("train", selected_proof), ("valid", []), ("test", [])):
            (target / f"{split}.json").write_text(
                json.dumps(rows, indent=2, ensure_ascii=False) + "\n"
            )
        for name, rows in (
            ("train_t5_plain_format.json", selected_plain),
            ("valid_t5_plain_format.json", []),
            ("test_t5_plain_format.json", []),
        ):
            (target / name).write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n")
        (target / "balanced_replay_rows.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in selected_replay)
        )
        for artifact in ARTIFACTS:
            shutil.copy2(source / artifact, target / artifact)

        config = json.loads((source / "config.json").read_text())
        config.update(
            {
                "validation": False,
                "train_rows": 541,
                "valid_rows": 0,
                "test_rows": 0,
                "single_expansion_source": args.expansion,
                "single_curriculum_parent": args.source_task,
                "data_revision": "java-expansion-benchmark-specific-single-curriculum-v1",
            }
        )
        for key in ("plain_loader", "proof_loader"):
            if key in config:
                config[key] = config[key].replace(args.source_task, args.target_task)
        (target / "config.json").write_text(json.dumps(config, indent=2) + "\n")

        source_manifest_path = source / "balanced_replay_manifest.json"
        if not source_manifest_path.exists():
            source_manifest_path = source / "pair_curriculum_manifest.json"
        source_manifest = json.loads(source_manifest_path.read_text())
        manifest = {
            "task": args.target_task,
            "source_task": args.source_task,
            "policy": (
                "retain exactly one frozen 541-occurrence expansion materialization; "
                "preserve source order and proof/plain/replay alignment; no MBJP replay; "
                "no validation or test rows"
            ),
            "expansion": args.expansion,
            "effective_rows_by_source": {args.expansion: 541},
            "effective_train_rows": 541,
            "validation_rows": 0,
            "test_rows": 0,
            "selection_uses_model_outputs": False,
            "selection_uses_test_outcomes": False,
            "source_split_uses_gold_ir_grammar_shape": source_manifest.get(
                "source_split_uses_gold_ir_grammar_shape", False
            ),
            "source_manifest": source_manifest_path.name,
            "source_manifest_sha256": sha256(source_manifest_path),
            "source_replay_rows_sha256": sha256(source / "balanced_replay_rows.jsonl"),
            "proof_train_sha256": sha256(target / "train.pkl"),
            "plain_train_sha256": sha256(target / "train_t5_plain_format.json"),
            "artifact_sha256": {name: sha256(target / name) for name in ARTIFACTS},
        }
        (target / "single_curriculum_manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n"
        )
        print(json.dumps(manifest, indent=2))
    except Exception:
        shutil.rmtree(target)
        raise


if __name__ == "__main__":
    main()
