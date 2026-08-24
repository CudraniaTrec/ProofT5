#!/usr/bin/env python3
"""Split an audited three-source curriculum into two-source training tasks.

The source curriculum already contains exactly 541 deterministic materialized
occurrences per source.  This builder keeps one base source plus one expansion,
preserving row order, multiplicity, proof/plain alignment, and all replay
metadata.  The base source defaults to MBJP for backward compatibility.  It
creates no validation or test rows.
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
        "--base-source",
        choices=("mbjp", "humaneval_java", "transcoder_gfg"),
        default="mbjp",
    )
    parser.add_argument("--expansion", choices=("humaneval_java", "transcoder_gfg"), required=True)
    parser.add_argument("--target-task", required=True)
    parser.add_argument("--expansion-copies", type=int, default=1)
    args = parser.parse_args()
    if args.expansion_copies < 1:
        raise ValueError("--expansion-copies must be at least one")
    if args.base_source == args.expansion:
        raise ValueError("--base-source and --expansion must differ")

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
    keep_sources = {args.base_source, args.expansion}
    base_indices = [i for i, row in enumerate(replay) if row["source"] in keep_sources]
    expansion_indices = [i for i in base_indices if replay[i]["source"] == args.expansion]
    indices = base_indices + expansion_indices * (args.expansion_copies - 1)
    selected_proof = [proof[i] for i in indices]
    selected_plain = [plain[i] for i in indices]
    selected_replay = []
    for new_index, old_index in enumerate(indices):
        row = dict(replay[old_index])
        row["source_materialized_index"] = row["materialized_index"]
        row["materialized_index"] = new_index
        row["pair_expansion_copies"] = args.expansion_copies
        if row["source"] == args.expansion:
            occurrence = sum(
                replay[prior]["source"] == args.expansion
                for prior in indices[:new_index]
            )
            row["pair_expansion_copy"] = occurrence // len(expansion_indices)
        selected_replay.append(row)
    counts = {
        source_name: sum(row["source"] == source_name for row in selected_replay)
        for source_name in sorted(keep_sources)
    }
    expected_counts = {
        args.base_source: 541,
        args.expansion: 541 * args.expansion_copies,
    }
    expected_rows = sum(expected_counts.values())
    if counts != expected_counts or len(indices) != expected_rows:
        raise RuntimeError(f"unexpected pair materialization: {counts}")

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
                "train_rows": expected_rows,
                "valid_rows": 0,
                "test_rows": 0,
                "pair_base_source": args.base_source,
                "pair_expansion_source": args.expansion,
                "pair_expansion_copies": args.expansion_copies,
                "pair_curriculum_parent": args.source_task,
                "data_revision": "java-expansion-benchmark-specific-pair-curriculum-v1",
            }
        )
        for key in ("plain_loader", "proof_loader"):
            if key in config:
                config[key] = config[key].replace(args.source_task, args.target_task)
        (target / "config.json").write_text(json.dumps(config, indent=2) + "\n")
        source_manifest = json.loads((source / "balanced_replay_manifest.json").read_text())
        manifest = {
            "task": args.target_task,
            "source_task": args.source_task,
            "policy": (
                f"retain the frozen 541-occurrence {args.base_source} materialization and "
                f"{args.expansion_copies} copies of the frozen 541-occurrence "
                "expansion materialization; preserve the original pair as "
                "the first copy and append deterministic expansion copies; "
                "no validation or test rows"
            ),
            "base_source": args.base_source,
            "expansion": args.expansion,
            "expansion_copies": args.expansion_copies,
            "effective_rows_by_source": counts,
            "effective_train_rows": len(indices),
            "validation_rows": 0,
            "test_rows": 0,
            "selection_uses_model_outputs": False,
            "selection_uses_test_outcomes": False,
            "source_split_uses_gold_ir_grammar_shape": source_manifest.get(
                "source_split_uses_gold_ir_grammar_shape", False
            ),
            "source_split_uses_gold_canonical_java": source_manifest.get(
                "source_split_uses_gold_canonical_java", False
            ),
            "source_split_uses_gold_operators_api_calls_and_literals": source_manifest.get(
                "source_split_uses_gold_operators_api_calls_and_literals", False
            ),
            "selection_uses_test_gold_solution_or_ir": source_manifest.get(
                "selection_uses_test_gold_solution_or_ir", False
            ),
            "source_replay_manifest_sha256": sha256(source / "balanced_replay_manifest.json"),
            "source_replay_rows_sha256": sha256(source / "balanced_replay_rows.jsonl"),
            "proof_train_sha256": sha256(target / "train.pkl"),
            "plain_train_sha256": sha256(target / "train_t5_plain_format.json"),
            "artifact_sha256": {name: sha256(target / name) for name in ARTIFACTS},
        }
        (target / "pair_curriculum_manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n"
        )
        print(json.dumps(manifest, indent=2))
    except Exception:
        shutil.rmtree(target)
        raise


if __name__ == "__main__":
    main()
