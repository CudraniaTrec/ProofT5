#!/usr/bin/env python3
import hashlib
import sys
import tempfile
from pathlib import Path

import torch

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from run import save_model, snapshot_saved_model


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    with tempfile.TemporaryDirectory(prefix="prooft5-snapshot-") as temporary:
        root = Path(temporary) / "root"
        snapshots = Path(temporary) / "snapshots"
        model = torch.nn.Linear(4, 3, bias=False)

        save_model(model, f"{root}/", model_type="last")
        root_checkpoint = root / "last_model.ckpt"
        snapshot_saved_model(f"{root}/", "last", f"{snapshots}/", "epoch0")
        epoch_checkpoint = snapshots / "epoch0_model.ckpt"
        first_root_sha = sha256(root_checkpoint)
        first_epoch_sha = sha256(epoch_checkpoint)
        assert first_root_sha == first_epoch_sha
        snapshot_saved_model(f"{root}/", "last", f"{root}/", "best")
        best_checkpoint = root / "best_model.ckpt"
        assert sha256(best_checkpoint) == first_root_sha

        with torch.no_grad():
            model.weight.add_(1.0)
        save_model(model, f"{root}/", model_type="last")
        second_root_sha = sha256(root_checkpoint)
        second_epoch_sha = sha256(epoch_checkpoint)
        assert second_root_sha != first_root_sha
        assert second_epoch_sha == first_epoch_sha
        assert sha256(best_checkpoint) == first_root_sha
        assert not list(root.glob("*.tmp-*"))
        assert not list(snapshots.glob("*.tmp-*"))

        print(
            {
                "initial_root_sha256": first_root_sha,
                "epoch_snapshot_sha256": first_epoch_sha,
                "updated_root_sha256": second_root_sha,
                "snapshot_immutable_after_root_update": True,
                "best_snapshot_immutable_after_root_update": True,
                "temporary_files_remaining": 0,
            }
        )


if __name__ == "__main__":
    main()
