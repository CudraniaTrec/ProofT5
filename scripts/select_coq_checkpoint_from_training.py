#!/usr/bin/env python3
"""Select a no-validation ProofT5 Coq checkpoint using training loss only."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pickle
from collections import defaultdict
from pathlib import Path

try:
    from scripts.audit_complete_coqview_training import (
        audit_runtime_shards,
        expected_partition,
    )
except ModuleNotFoundError:
    from audit_complete_coqview_training import (
        audit_runtime_shards,
        expected_partition,
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metrics", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--target-dir", type=Path, required=True)
    parser.add_argument("--expected-passes", type=int, required=True)
    parser.add_argument("--expected-batches-per-pass", type=int, required=True)
    parser.add_argument("--parent", required=True)
    parser.add_argument("--learning-rate", type=float, required=True)
    parser.add_argument("--train-pickle", type=Path)
    parser.add_argument("--runtime-dir", type=Path)
    parser.add_argument("--ranks", type=int, default=8)
    parser.add_argument("--expected-base-seed", type=int)
    args = parser.parse_args()

    if bool(args.train_pickle) != bool(args.runtime_dir):
        raise RuntimeError("--train-pickle and --runtime-dir must be provided together")
    parent_checkpoint = Path("Utils/models") / f"Model{args.parent}" / "last_model.ckpt"
    if not parent_checkpoint.is_file():
        raise FileNotFoundError(parent_checkpoint)

    if args.target_dir.exists():
        raise FileExistsError(f"refusing to overwrite {args.target_dir}")
    grouped = defaultdict(list)
    configuration_records = []
    for line in args.metrics.read_text().splitlines():
        row = json.loads(line)
        if "loss" in row:
            grouped[int(row["epoch"])].append(row)
        if row.get("event") == "training_configuration":
            configuration_records.append(row)
    if args.expected_base_seed is not None:
        expected_configuration = {
            "base_seed": args.expected_base_seed,
            "rank_seeds": [args.expected_base_seed + rank for rank in range(args.ranks)],
            "world_size": args.ranks,
        }
        if len(configuration_records) != 1 or any(
            configuration_records[0].get(key) != value
            for key, value in expected_configuration.items()
        ):
            raise RuntimeError(
                f"training seed configuration does not match {expected_configuration}"
            )
    expected_epochs = list(range(args.expected_passes))
    if sorted(grouped) != expected_epochs:
        raise RuntimeError(f"unexpected loss epochs: {sorted(grouped)}")
    pass_losses = []
    pass_active_target_tokens = []
    padding_rows = []
    for epoch in expected_epochs:
        rows = grouped[epoch]
        if len(rows) != args.expected_batches_per_pass:
            raise RuntimeError(
                f"epoch {epoch} has {len(rows)} batches, expected {args.expected_batches_per_pass}"
            )
        if [int(row["batch"]) for row in rows] != list(range(args.expected_batches_per_pass)):
            raise RuntimeError(f"epoch {epoch} batch indices are incomplete")
        required_global_fields = (
            "global_token_weighted_loss",
            "global_active_target_tokens",
            "rank_active_target_tokens",
            "rank_losses",
            "distributed_token_mean_backward_scale",
        )
        for batch_index, row in enumerate(rows):
            missing = [key for key in required_global_fields if key not in row]
            if missing:
                raise RuntimeError(
                    f"epoch {epoch} batch {batch_index} lacks globally aggregated "
                    f"training-loss fields: {missing}"
                )
            if float(row["loss"]) != float(row["global_token_weighted_loss"]):
                raise RuntimeError(
                    f"epoch {epoch} batch {batch_index} loss is not the global "
                    "token-weighted loss"
                )
            if sum(int(value) for value in row["rank_active_target_tokens"]) != int(
                row["global_active_target_tokens"]
            ):
                raise RuntimeError(
                    f"epoch {epoch} batch {batch_index} target-token accounting "
                    "is inconsistent"
                )
            if len(row["rank_active_target_tokens"]) != len(row["rank_losses"]):
                raise RuntimeError(
                    f"epoch {epoch} batch {batch_index} rank metric lengths differ"
                )
            expected_scale = (
                len(row["rank_active_target_tokens"])
                * int(row["rank_active_target_tokens"][0])
                / int(row["global_active_target_tokens"])
            )
            if abs(
                float(row["distributed_token_mean_backward_scale"])
                - expected_scale
            ) > 1e-12:
                raise RuntimeError(
                    f"epoch {epoch} batch {batch_index} has an inconsistent "
                    "distributed backward scale"
                )
        active_target_tokens = sum(
            int(row["global_active_target_tokens"]) for row in rows
        )
        if active_target_tokens <= 0:
            raise RuntimeError(f"epoch {epoch} has no active target tokens")
        pass_active_target_tokens.append(active_target_tokens)
        pass_losses.append(
            sum(
                float(row["global_token_weighted_loss"])
                * int(row["global_active_target_tokens"])
                for row in rows
            )
            / active_target_tokens
        )
        padding_rows.append(
            sum(int(row.get("global_distributed_zero_loss_padding_rows", 0)) for row in rows)
        )
    if len(set(pass_active_target_tokens)) != 1:
        raise RuntimeError(
            "global active target-token count changed across complete passes: "
            f"{pass_active_target_tokens}"
        )
    if len(set(padding_rows)) != 1:
        raise RuntimeError(
            "distributed padding-row count changed across complete passes: "
            f"{padding_rows}"
        )
    selected_index = min(range(args.expected_passes), key=lambda i: (pass_losses[i], i))

    runtime_shard_audit = None
    if args.train_pickle:
        with args.train_pickle.open("rb") as handle:
            real_rows = len(pickle.load(handle))
        _, original_lengths, expected_padding = expected_partition(
            real_rows, args.ranks
        )
        runtime_shard_audit = audit_runtime_shards(
            args.train_pickle,
            args.runtime_dir,
            args.ranks,
            original_lengths,
            expected_padding,
        )

    run_dirs = [path for path in args.model_dir.iterdir() if path.is_dir()]
    if len(run_dirs) != 1:
        raise RuntimeError(f"expected one timestamped checkpoint directory, got {run_dirs}")
    if selected_index + 1 == args.expected_passes:
        source = run_dirs[0] / "final_model.ckpt"
    else:
        source = run_dirs[0] / f"epoch{selected_index + 1}_model.ckpt"
    if not source.is_file():
        raise FileNotFoundError(source)
    args.target_dir.mkdir(parents=True)
    target = args.target_dir / "last_model.ckpt"
    os.link(source, target)
    manifest = {
        "selected_model": args.target_dir.name.removeprefix("Model"),
        "source_model": args.model_dir.name.removeprefix("Model"),
        "source_checkpoint": str(source),
        "metrics": str(args.metrics),
        "metrics_sha256": sha256(args.metrics),
        "parent_checkpoint": args.parent,
        "parent_checkpoint_path": str(parent_checkpoint.resolve()),
        "parent_checkpoint_sha256": sha256(parent_checkpoint),
        "learning_rate": args.learning_rate,
        "base_seed": args.expected_base_seed,
        "rank_seeds": (
            [args.expected_base_seed + rank for rank in range(args.ranks)]
            if args.expected_base_seed is not None
            else None
        ),
        "completed_passes": args.expected_passes,
        "batches_per_pass": args.expected_batches_per_pass,
        "selection_policy": (
            "minimum global active-target-token-weighted complete-pass training "
            "loss; no validation or test scores used"
        ),
        "snapshot_semantics": (
            "epochN_model.ckpt is saved before epoch N and contains N completed "
            "passes; final_model.ckpt contains all requested passes"
        ),
        "selected_pass_one_based": selected_index + 1,
        "selected_global_token_weighted_training_loss": pass_losses[selected_index],
        "global_token_weighted_training_loss_by_pass": pass_losses,
        "global_active_target_tokens_by_pass": pass_active_target_tokens,
        "global_padding_rows_by_pass": padding_rows,
        "last_model_sha256": sha256(target),
        "storage": "last_model.ckpt is a hard link to the selected source checkpoint",
        "runtime_shard_audit": runtime_shard_audit,
    }
    (args.target_dir / "selection_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
