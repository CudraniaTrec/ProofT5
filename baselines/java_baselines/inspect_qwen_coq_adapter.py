from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import torch


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect(checkpoint: Path) -> dict:
    state = torch.load(checkpoint, map_location="cpu", weights_only=True)
    projection = state["coq_projection.weight"].float()
    gate = state["coq_gate"].float()
    return {
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": sha256(checkpoint),
        "coq_gate": float(gate.item()),
        "coq_projection_shape": list(projection.shape),
        "coq_projection_l2_norm": float(torch.linalg.vector_norm(projection).item()),
        "coq_projection_nonzero_parameters": int(torch.count_nonzero(projection).item()),
        "coq_projection_parameters": int(projection.numel()),
        "interpretation": (
            "A nonzero projection norm proves that the selected representation-only "
            "Coq branch is active; it does not by itself establish test accuracy."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Record the learned Qwen causal-DSL Coq adapter state."
    )
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = inspect(args.checkpoint)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
