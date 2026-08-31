"""Resumably download the four large decoder-only checkpoints.

The ordinary ``snapshot_download`` call can return an existing ``local_dir``
when the remote endpoint is unavailable.  This helper therefore verifies every
weight shard against the repository index before declaring a model complete and
keeps retrying transient proxy failures.  It never removes partial files.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from huggingface_hub import HfApi, snapshot_download


ROOT = Path("/data2/x/hzc/hf_models")
TOKEN_PATH = Path("/home/zchuang/.cache/huggingface/token")
MODELS = (
    ("Qwen/Qwen3-14B-Base", "Qwen3-14B-Base"),
    ("Qwen/Qwen3-30B-A3B-Base", "Qwen3-30B-A3B-Base"),
    ("Qwen/Qwen3-32B", "Qwen3-32B"),
    ("allenai/Olmo-3-1125-32B", "Olmo-3-1125-32B"),
)
MAX_ATTEMPTS = 60
RETRY_SECONDS = 60


def expected_shards(repo: str, token: str) -> dict[str, int]:
    files = HfApi().list_repo_tree(repo, recursive=True, token=token)
    result = {}
    for item in files:
        name = getattr(item, "path", "")
        size = getattr(item, "size", None)
        if name.endswith(".safetensors") and size:
            result[Path(name).name] = int(size)
    return result


def complete(local_dir: Path, expected: dict[str, int]) -> bool:
    index = local_dir / "model.safetensors.index.json"
    if not index.is_file():
        return False
    try:
        weight_map = json.loads(index.read_text()).get("weight_map", {})
    except (OSError, ValueError):
        return False
    names = sorted(set(weight_map.values()))
    if not names or set(names) - set(expected):
        return False
    for name in names:
        path = local_dir / name
        if not path.is_file() or path.stat().st_size != expected[name]:
            return False
    return True


def main() -> None:
    token = TOKEN_PATH.read_text().strip()
    # Resolve sizes once when the endpoint is available.  If this first call
    # fails, the loop below retries it without treating a partial directory as
    # a completed snapshot.
    expected: dict[str, dict[str, int]] = {}
    for repo, _ in MODELS:
        try:
            expected[repo] = expected_shards(repo, token)
        except Exception as exc:  # pragma: no cover - network dependent
            print(f"index fetch failed for {repo}: {type(exc).__name__}: {exc}", flush=True)

    for attempt in range(1, MAX_ATTEMPTS + 1):
        all_done = True
        print(f"attempt {attempt}/{MAX_ATTEMPTS}", flush=True)
        for repo, dest in MODELS:
            local_dir = ROOT / dest
            sizes = expected.get(repo, {})
            if sizes and complete(local_dir, sizes):
                print(f"complete {repo}", flush=True)
                continue
            all_done = False
            try:
                snapshot_download(
                    repo_id=repo,
                    local_dir=str(local_dir),
                    token=token,
                    max_workers=4,
                )
                if not sizes:
                    sizes = expected_shards(repo, token)
                    expected[repo] = sizes
                print(
                    f"download returned {repo}; verified={complete(local_dir, sizes)}",
                    flush=True,
                )
            except Exception as exc:  # pragma: no cover - network dependent
                print(f"download failed for {repo}: {type(exc).__name__}: {exc}", flush=True)
        if all_done:
            print("all models complete", flush=True)
            return
        if attempt < MAX_ATTEMPTS:
            time.sleep(RETRY_SECONDS)
    raise SystemExit("download retries exhausted; no incomplete snapshot was promoted")


if __name__ == "__main__":
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
    os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "600")
    os.environ.setdefault("HF_HUB_ETAG_TIMEOUT", "120")
    main()

