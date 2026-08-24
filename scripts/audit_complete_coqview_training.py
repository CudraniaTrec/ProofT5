#!/usr/bin/env python3
"""Audit that a no-validation distributed CoqView run covered every pass."""

import argparse
import collections
import hashlib
import json
import math
import pickle
from pathlib import Path


def expected_partition(real_rows, ranks):
    batches_per_rank = (real_rows + ranks - 1) // ranks
    original = [batches_per_rank] * ranks
    for rank in range(batches_per_rank * ranks - real_rows):
        original[rank] -= 1
    padding = [batches_per_rank - rows for rows in original]
    return batches_per_rank, original, padding


def row_digest(row):
    clean = dict(row)
    clean.pop("_distributed_zero_loss_padding", None)
    return hashlib.sha256(pickle.dumps(clean, protocol=4)).hexdigest()


def validate_rank_loss_accounting(record, ranks, label="record"):
    active = record.get("coqview_rank_active_targets")
    loss_sums = record.get("coqview_rank_loss_sums")
    if not isinstance(active, list) or len(active) != ranks:
        raise RuntimeError(f"{label}: missing {ranks}-rank active-target accounting")
    if not isinstance(loss_sums, list) or len(loss_sums) != ranks:
        raise RuntimeError(f"{label}: missing {ranks}-rank loss-sum accounting")
    active = [int(value) for value in active]
    loss_sums = [float(value) for value in loss_sums]
    if any(value < 0 for value in active) or not all(
        math.isfinite(value) for value in loss_sums
    ):
        raise RuntimeError(f"{label}: invalid per-rank loss accounting")
    global_active = int(record.get("coqview_global_active_targets", 0))
    if global_active <= 0 or sum(active) != global_active:
        raise RuntimeError(
            f"{label}: rank active targets sum to {sum(active)}, not {global_active}"
        )
    reconstructed = sum(loss_sums) / global_active
    logged = float(record["loss"])
    if not math.isclose(reconstructed, logged, rel_tol=1e-6, abs_tol=1e-9):
        raise RuntimeError(
            f"{label}: reconstructed global loss {reconstructed} != logged {logged}"
        )
    return reconstructed


def audit_runtime_shards(train_pickle, runtime_dir, ranks, original_lengths, padding):
    source_rows = pickle.loads(train_pickle.read_bytes())
    source_counts = collections.Counter(row_digest(row) for row in source_rows)
    runtime_counts = collections.Counter()
    observed_lengths = []
    observed_padding = []
    padding_source_misses = 0
    for rank in range(ranks):
        shard_path = runtime_dir / f"data_train{rank}.pkl"
        shard = pickle.loads(shard_path.read_bytes())
        observed_lengths.append(len(shard))
        rank_padding = 0
        for row in shard:
            digest = row_digest(row)
            if row.get("_distributed_zero_loss_padding", False):
                rank_padding += 1
                if digest not in source_counts:
                    padding_source_misses += 1
            else:
                runtime_counts[digest] += 1
        observed_padding.append(rank_padding)

    expected_lengths = [rows + pads for rows, pads in zip(original_lengths, padding)]
    missing = sum((source_counts - runtime_counts).values())
    extra = sum((runtime_counts - source_counts).values())
    if len(source_rows) != sum(original_lengths):
        raise SystemExit(
            f"train pickle has {len(source_rows)} rows, expected {sum(original_lengths)}"
        )
    if observed_lengths != expected_lengths:
        raise SystemExit(
            f"runtime shard lengths {observed_lengths} != expected {expected_lengths}"
        )
    if observed_padding != padding:
        raise SystemExit(
            f"runtime padding {observed_padding} != expected {padding}"
        )
    if runtime_counts != source_counts:
        raise SystemExit(
            f"runtime/source row multisets differ: missing={missing}, extra={extra}"
        )
    if padding_source_misses:
        raise SystemExit(
            f"{padding_source_misses} padding rows do not copy a source row"
        )
    return {
        "train_pickle": str(train_pickle),
        "runtime_dir": str(runtime_dir),
        "source_rows": len(source_rows),
        "runtime_real_rows": sum(runtime_counts.values()),
        "source_unique_content_hashes": len(source_counts),
        "runtime_unique_content_hashes": len(runtime_counts),
        "content_multiset_exact_match": True,
        "missing_content_occurrences": 0,
        "extra_content_occurrences": 0,
        "runtime_shard_lengths": observed_lengths,
        "runtime_padding_counts": observed_padding,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("metrics", type=Path)
    parser.add_argument("--real_rows", type=int, required=True)
    parser.add_argument("--ranks", type=int, default=8)
    parser.add_argument("--passes", type=int, required=True)
    parser.add_argument("--expected_active_targets_per_pass", type=int, default=0)
    parser.add_argument("--train_pickle", type=Path)
    parser.add_argument("--runtime_dir", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        help="optionally persist the audited JSON summary",
    )
    parser.add_argument(
        "--allow_later_records",
        action="store_true",
        help="audit the first requested passes while a later pass is in progress",
    )
    args = parser.parse_args()

    if args.real_rows < 1 or args.ranks < 1 or args.passes < 1:
        raise SystemExit("real_rows, ranks, and passes must all be positive")
    if bool(args.train_pickle) != bool(args.runtime_dir):
        raise SystemExit("--train_pickle and --runtime_dir must be provided together")

    records = [json.loads(line) for line in args.metrics.read_text().splitlines()]
    all_losses = [record for record in records if "loss" in record]
    later_loss_records_ignored = 0
    if args.allow_later_records:
        epoch_order = sorted({int(record["epoch"]) for record in all_losses})
        selected_epochs = epoch_order[: args.passes]
        losses = [
            record
            for record in all_losses
            if int(record["epoch"]) in selected_epochs
        ]
        later_loss_records_ignored = len(all_losses) - len(losses)
    else:
        losses = all_losses
    batches_per_rank, original_lengths, expected_padding = expected_partition(
        args.real_rows, args.ranks
    )
    expected_loss_records = args.passes * batches_per_rank
    if len(losses) != expected_loss_records:
        raise SystemExit(
            f"loss record count {len(losses)} != {expected_loss_records} "
            f"({args.passes} passes x {batches_per_rank} batches)"
        )

    observed_epochs = sorted({int(record["epoch"]) for record in losses})
    if len(observed_epochs) != args.passes:
        raise SystemExit(
            f"observed epochs {observed_epochs} do not contain {args.passes} passes"
        )

    per_epoch = {}
    for epoch in observed_epochs:
        epoch_records = [
            record for record in losses if int(record["epoch"]) == epoch
        ]
        observed_batches = [int(record["batch"]) for record in epoch_records]
        if observed_batches != list(range(batches_per_rank)):
            raise SystemExit(
                f"epoch {epoch} batch ids are incomplete or out of order: "
                f"{observed_batches}"
            )
        if not all(math.isfinite(float(record["loss"])) for record in epoch_records):
            raise SystemExit(f"epoch {epoch} contains a non-finite loss")

        padding = [0] * args.ranks
        active_targets = 0
        active_target_weighted_loss_sum = 0.0
        unweighted_loss_sum = 0.0
        for record in epoch_records:
            validate_rank_loss_accounting(
                record,
                args.ranks,
                f"epoch {epoch} batch {record['batch']}",
            )
            rank_padding = record.get("rank_distributed_zero_loss_padding_rows")
            if not isinstance(rank_padding, list) or len(rank_padding) != args.ranks:
                raise SystemExit(
                    f"epoch {epoch} batch {record['batch']} lacks {args.ranks}-rank "
                    "padding evidence"
                )
            for rank, value in enumerate(rank_padding):
                padding[rank] += int(value)
            batch_active_targets = int(
                record.get("coqview_global_active_targets", 0)
            )
            if batch_active_targets <= 0:
                raise SystemExit(
                    f"epoch {epoch} batch {record['batch']} has no active target"
                )
            active_targets += batch_active_targets
            batch_loss = float(record["loss"])
            active_target_weighted_loss_sum += batch_loss * batch_active_targets
            unweighted_loss_sum += batch_loss
        if padding != expected_padding:
            raise SystemExit(
                f"epoch {epoch} padding {padding} != expected {expected_padding}"
            )
        if (
            args.expected_active_targets_per_pass > 0
            and active_targets != args.expected_active_targets_per_pass
        ):
            raise SystemExit(
                f"epoch {epoch} active targets {active_targets} != expected "
                f"{args.expected_active_targets_per_pass}"
            )
        per_epoch[str(epoch)] = {
            "batches": len(epoch_records),
            "padding_per_rank": padding,
            "active_targets": active_targets,
            "active_target_weighted_mean_loss": (
                active_target_weighted_loss_sum / active_targets
            ),
            "unweighted_mean_batch_loss": unweighted_loss_sum / len(epoch_records),
            "first_loss": float(epoch_records[0]["loss"]),
            "last_loss": float(epoch_records[-1]["loss"]),
        }

    summary = {
        "status": "ok",
        "metrics": str(args.metrics),
        "real_rows": args.real_rows,
        "ranks": args.ranks,
        "passes": args.passes,
        "batches_per_rank_per_pass": batches_per_rank,
        "loss_records": len(losses),
        "later_loss_records_ignored": later_loss_records_ignored,
        "original_shard_lengths": original_lengths,
        "expected_padding_per_rank_per_pass": expected_padding,
        "expected_active_targets_per_pass": (
            args.expected_active_targets_per_pass or None
        ),
        "epochs": per_epoch,
    }
    if args.train_pickle:
        summary["runtime_shard_audit"] = audit_runtime_shards(
            args.train_pickle,
            args.runtime_dir,
            args.ranks,
            original_lengths,
            expected_padding,
        )
    rendered = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered)
    print(rendered, end="")


if __name__ == "__main__":
    main()
