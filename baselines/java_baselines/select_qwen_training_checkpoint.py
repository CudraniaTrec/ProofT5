from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import defaultdict
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def select(args: argparse.Namespace) -> dict:
    metric_rows = [
        json.loads(line)
        for line in Path(args.metrics).read_text().splitlines()
        if line.strip()
    ]
    losses = defaultdict(list)
    for row in metric_rows:
        if "loss" in row and "epoch" in row:
            losses[int(row["epoch"])].append(
                (
                    float(row["loss"]),
                    int(row.get("global_active_target_tokens", 1)),
                )
            )
    model_root = Path(args.model_root)
    if args.run_directory:
        run_directory = Path(args.run_directory)
    else:
        candidates = sorted(path for path in model_root.iterdir() if path.is_dir())
        if len(candidates) != 1:
            raise RuntimeError(
                f"expected exactly one checkpoint run directory under {model_root}; "
                f"found {[path.name for path in candidates]}"
            )
        run_directory = candidates[0]
    specifications = [
        ("epoch5", 4),
        ("epoch10", 9),
        ("epoch15", 14),
        ("epoch20", 19),
        ("final", 20),
    ]
    candidates = []
    for checkpoint, metric_epoch in specifications:
        path = run_directory / f"{checkpoint}_model.ckpt"
        if not path.is_file() or not losses[metric_epoch]:
            continue
        candidates.append(
            {
                "checkpoint": checkpoint,
                "checkpoint_path": str(path),
                "metric_epoch": metric_epoch,
                "global_training_token_loss": sum(
                    loss * tokens for loss, tokens in losses[metric_epoch]
                )
                / sum(tokens for _, tokens in losses[metric_epoch]),
                "active_target_tokens": sum(
                    tokens for _, tokens in losses[metric_epoch]
                ),
                "metric_batches": len(losses[metric_epoch]),
            }
        )
    if not candidates:
        raise RuntimeError("no prespecified checkpoint has complete training metrics")
    chosen = min(candidates, key=lambda item: item["global_training_token_loss"])
    source = Path(chosen["checkpoint_path"])
    target = model_root / "selected_model.ckpt"
    if target.exists():
        raise FileExistsError(f"refusing to overwrite frozen selection: {target}")
    temporary = target.with_name(f"{target.name}.tmp-{os.getpid()}")
    os.link(source, temporary)
    os.replace(temporary, target)
    result = {
        "selection_policy": (
            "minimum mean global training-token loss at prespecified completed "
            "epochs; validation and test generation were never run"
        ),
        "metrics": args.metrics,
        "model_root": str(model_root),
        "run_directory": str(run_directory),
        "candidates": candidates,
        "selected": chosen,
        "selected_path": str(target),
        "selected_sha256": sha256(target),
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Select a Qwen causal DSL checkpoint without test-set tuning."
    )
    parser.add_argument("--metrics", required=True)
    parser.add_argument("--model_root", required=True)
    parser.add_argument("--run_directory", default="")
    parser.add_argument("--output", required=True)
    select(parser.parse_args())


if __name__ == "__main__":
    main()
