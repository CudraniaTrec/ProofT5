#!/usr/bin/env python3
"""Select a no-validation CoqView checkpoint using training loss only."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path

try:
    from scripts.audit_complete_coqview_training import validate_rank_loss_accounting
except ModuleNotFoundError:
    from audit_complete_coqview_training import validate_rank_loss_accounting


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def checkpoint_for_pass(model_dir: Path, completed_pass: int, total_passes: int) -> Path:
    if completed_pass == total_passes:
        path = model_dir / "last_model.ckpt"
        if not path.is_file():
            raise SystemExit(f"missing final checkpoint: {path}")
        return path
    matches = list(model_dir.glob(f"*/epoch{completed_pass}_model.ckpt"))
    if len(matches) != 1:
        raise SystemExit(
            f"pass {completed_pass}: expected one epoch{completed_pass} checkpoint, "
            f"found {len(matches)}"
        )
    return matches[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("metrics", type=Path)
    parser.add_argument("model_dir", type=Path)
    parser.add_argument("selected_model_dir", type=Path)
    parser.add_argument("--passes", type=int, required=True)
    parser.add_argument("--batches_per_pass", type=int, required=True)
    parser.add_argument("--expected_active_targets_per_pass", type=int, required=True)
    parser.add_argument("--learning_rate", type=float, required=True)
    parser.add_argument("--ranks", type=int, default=8)
    parser.add_argument("--expected-base-seed", type=int)
    parser.add_argument("--parent")
    args = parser.parse_args()

    parent_checkpoint = None
    if args.parent:
        parent_checkpoint = (
            Path("Utils/models") / f"Model{args.parent}" / "last_model.ckpt"
        )
        if not parent_checkpoint.is_file():
            raise FileNotFoundError(parent_checkpoint)

    records = []
    configuration_records = []
    for line in args.metrics.read_text().splitlines():
        record = json.loads(line)
        if "loss" in record:
            records.append(record)
        if record.get("event") == "training_configuration":
            configuration_records.append(record)
    if args.expected_base_seed is not None:
        expected_configuration = {
            "base_seed": args.expected_base_seed,
            "rank_seeds": [
                args.expected_base_seed + rank for rank in range(args.ranks)
            ],
            "world_size": args.ranks,
        }
        if len(configuration_records) != 1 or any(
            configuration_records[0].get(key) != value
            for key, value in expected_configuration.items()
        ):
            raise SystemExit(
                f"training seed configuration does not match {expected_configuration}"
            )
    expected = args.passes * args.batches_per_pass
    if len(records) != expected:
        raise SystemExit(f"loss record count {len(records)} != {expected}")

    candidates = []
    for epoch in range(args.passes):
        rows = [row for row in records if int(row["epoch"]) == epoch]
        batches = [int(row["batch"]) for row in rows]
        if batches != list(range(args.batches_per_pass)):
            raise SystemExit(f"epoch {epoch}: incomplete or unordered batches")
        active = sum(int(row.get("coqview_global_active_targets", 0)) for row in rows)
        if active != args.expected_active_targets_per_pass:
            raise SystemExit(
                f"epoch {epoch}: active targets {active} != "
                f"{args.expected_active_targets_per_pass}"
            )
        losses = [float(row["loss"]) for row in rows]
        if not all(math.isfinite(loss) for loss in losses):
            raise SystemExit(f"epoch {epoch}: non-finite loss")
        for row in rows:
            validate_rank_loss_accounting(
                row,
                args.ranks,
                f"epoch {epoch} batch {row['batch']}",
            )
        weighted = sum(
            loss * int(row["coqview_global_active_targets"])
            for loss, row in zip(losses, rows)
        ) / active
        completed_pass = epoch + 1
        checkpoint = checkpoint_for_pass(
            args.model_dir, completed_pass, args.passes
        )
        candidates.append(
            {
                "completed_passes": completed_pass,
                "training_epoch": epoch,
                "active_targets": active,
                "active_target_weighted_mean_loss": weighted,
                "unweighted_mean_batch_loss": sum(losses) / len(losses),
                "checkpoint": str(checkpoint),
            }
        )

    selected = min(
        candidates,
        key=lambda item: (
            item["active_target_weighted_mean_loss"],
            item["completed_passes"],
        ),
    )
    source = Path(selected["checkpoint"])
    if args.selected_model_dir.exists():
        raise SystemExit(f"refusing to overwrite {args.selected_model_dir}")
    args.selected_model_dir.mkdir(parents=True)
    target = args.selected_model_dir / "last_model.ckpt"
    os.link(source, target)
    digest = sha256(target)
    manifest = {
        "selected_model": args.selected_model_dir.name.removeprefix("Model"),
        "source_model_dir": str(args.model_dir),
        "source_checkpoint": str(source),
        "selected_checkpoint": str(target),
        "checkpoint_sha256": digest,
        "parent_checkpoint": args.parent,
        "parent_checkpoint_path": (
            str(parent_checkpoint.resolve()) if parent_checkpoint else None
        ),
        "parent_checkpoint_sha256": (
            sha256(parent_checkpoint) if parent_checkpoint else None
        ),
        "selection_policy": (
            "minimum active-target-weighted mean training loss over complete "
            "passes; no validation or test scores used"
        ),
        "snapshot_semantics": (
            "epochN_model.ckpt is saved before epoch N and therefore contains "
            "N completed passes; last_model.ckpt contains all requested passes"
        ),
        "learning_rate": args.learning_rate,
        "completed_passes": args.passes,
        "batches_per_pass": args.batches_per_pass,
        "expected_active_targets_per_pass": args.expected_active_targets_per_pass,
        "base_seed": args.expected_base_seed,
        "rank_seeds": (
            [args.expected_base_seed + rank for rank in range(args.ranks)]
            if args.expected_base_seed is not None
            else None
        ),
        "selected_completed_passes": selected["completed_passes"],
        "selected_active_target_weighted_mean_loss": selected[
            "active_target_weighted_mean_loss"
        ],
        "candidates": candidates,
        "metrics": str(args.metrics),
        "metrics_sha256": sha256(args.metrics),
    }
    (args.selected_model_dir / "selection_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
