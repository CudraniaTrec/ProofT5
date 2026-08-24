#!/usr/bin/env python3
"""Select an ordinary T5Gemma2 checkpoint using training loss only."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path


LOSS_RE = re.compile(r"\bepoch (\d+): loss=([0-9.eE+-]+)$")
ACCOUNTING_RE = re.compile(
    r"\bepoch (\d+): active_target_tokens=(\d+) batches=(\d+)$"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_complete_training_log(text: str, expected_passes: int):
    losses = []
    accounting = []
    for line in text.splitlines():
        stripped = line.strip()
        loss_match = LOSS_RE.search(stripped)
        if loss_match:
            losses.append((int(loss_match.group(1)), float(loss_match.group(2))))
        accounting_match = ACCOUNTING_RE.search(stripped)
        if accounting_match:
            accounting.append(
                (
                    int(accounting_match.group(1)),
                    int(accounting_match.group(2)),
                    int(accounting_match.group(3)),
                )
            )
    if [epoch for epoch, _ in losses] != list(range(expected_passes)):
        raise RuntimeError(f"incomplete or duplicate epoch losses: {losses}")
    if [epoch for epoch, _, _ in accounting] != list(range(expected_passes)):
        raise RuntimeError(
            f"incomplete or duplicate epoch token accounting: {accounting}"
        )
    if any(tokens <= 0 or batches <= 0 for _, tokens, batches in accounting):
        raise RuntimeError(f"invalid epoch token accounting: {accounting}")
    if len({tokens for _, tokens, _ in accounting}) != 1:
        raise RuntimeError(f"active target-token count changed across epochs: {accounting}")
    if len({batches for _, _, batches in accounting}) != 1:
        raise RuntimeError(f"batch count changed across epochs: {accounting}")
    return losses, accounting


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--target-dir", type=Path, required=True)
    parser.add_argument("--expected-passes", type=int, required=True)
    parser.add_argument("--parent", required=True)
    parser.add_argument("--learning-rate", type=float, required=True)
    parser.add_argument("--expected-seed", type=int)
    parser.add_argument(
        "--expected-target-mode",
        choices=("full", "solution"),
        help="Require and record the decoder target mode written by the training wrapper.",
    )
    args = parser.parse_args()

    if args.target_dir.exists():
        raise FileExistsError(f"refusing to overwrite {args.target_dir}")
    parent_path = Path(args.parent)
    parent_weight = parent_path / "model.safetensors"
    if not parent_weight.is_file():
        raise FileNotFoundError(parent_weight)
    losses, accounting = parse_complete_training_log(
        args.log.read_text(errors="replace"), args.expected_passes
    )
    if args.expected_seed is not None:
        marker = f"PLAIN_SEED={args.expected_seed}"
        if args.log.read_text(errors="replace").splitlines().count(marker) != 1:
            raise RuntimeError(f"training log does not contain exactly one {marker}")
    if args.expected_target_mode is not None:
        marker = f"PLAIN_TARGET_MODE={args.expected_target_mode}"
        if args.log.read_text(errors="replace").splitlines().count(marker) != 1:
            raise RuntimeError(f"training log does not contain exactly one {marker}")
    selected_epoch, selected_loss = min(losses, key=lambda value: (value[1], value[0]))
    run_dirs = [path for path in args.model_dir.iterdir() if path.is_dir()]
    if len(run_dirs) != 1:
        raise RuntimeError(f"expected one timestamped run directory, got {run_dirs}")
    source = run_dirs[0] / f"epoch_{selected_epoch}"
    if not (source / "model.safetensors").is_file():
        raise FileNotFoundError(source / "model.safetensors")
    shutil.copytree(source, args.target_dir)
    manifest = {
        "selected_model": args.target_dir.name,
        "source_model": args.model_dir.name,
        "source_checkpoint": str(source),
        "training_log": str(args.log),
        "training_log_sha256": sha256(args.log),
        "parent_checkpoint": args.parent,
        "parent_checkpoint_path": str(parent_path.resolve()),
        "parent_model_safetensors_sha256": sha256(parent_weight),
        "learning_rate": args.learning_rate,
        "seed": args.expected_seed,
        "target_mode": args.expected_target_mode,
        "candidate_reconstruction": (
            "exact audited input prompt concatenated with generated canonical_solution"
            if args.expected_target_mode == "solution"
            else "model generates the complete prompt plus canonical_solution"
        ),
        "completed_passes": args.expected_passes,
        "selection_policy": (
            "minimum active-target-token-weighted complete-epoch training loss; "
            "no validation or test scores used"
        ),
        "snapshot_semantics": (
            "epoch_N is saved after zero-based epoch N and contains N+1 "
            "completed passes"
        ),
        "selected_epoch_zero_based": selected_epoch,
        "selected_training_loss": selected_loss,
        "epoch_training_loss": [loss for _, loss in losses],
        "active_target_tokens_by_epoch": [tokens for _, tokens, _ in accounting],
        "batches_by_epoch": [batches for _, _, batches in accounting],
        "model_safetensors_sha256": sha256(args.target_dir / "model.safetensors"),
    }
    (args.target_dir / "selected_checkpoint.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
