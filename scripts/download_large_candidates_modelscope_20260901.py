#!/usr/bin/env python3
"""Resume the four planned large-model downloads through ModelScope.

Hugging Face is intermittently unreachable from this host, while the public
ModelScope mirrors expose the same repositories.  The script only writes to
the explicitly named incomplete candidate directories, preserves partial
files, and verifies every downloaded file against the ModelScope file index.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen


ROOT = Path("/data2/x/hzc/hf_models")
DEFAULTS = (
    ("Qwen/Qwen3-14B", "Qwen3-14B-Base"),
    ("Qwen/Qwen3-30B-A3B", "Qwen3-30B-A3B-Base"),
    ("Qwen/Qwen3-32B", "Qwen3-32B"),
    ("allenai/Olmo-3-1125-32B", "Olmo-3-1125-32B"),
)


def api_files(repo: str) -> list[dict]:
    url = (
        "https://www.modelscope.cn/api/v1/models/"
        f"{repo}/repo/files?Revision=master&Recursive=true&PageNumber=1&PageSize=100"
    )
    request = Request(url, headers={"User-Agent": "prooft5-major-revision/20260901"})
    with urlopen(request, timeout=60) as response:
        body = json.load(response)
    if body.get("Code") != 200:
        raise RuntimeError(f"ModelScope index failed for {repo}: {body}")
    files = body.get("Data", {}).get("Files", [])
    if not files:
        raise RuntimeError(f"ModelScope index is empty for {repo}")
    return files


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(16 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def complete(local: Path, files: list[dict]) -> tuple[bool, list[str]]:
    missing = []
    for item in files:
        path = local / item["Path"]
        size = item.get("Size")
        if not path.is_file() or (size is not None and path.stat().st_size != int(size)):
            missing.append(item["Path"])
    return not missing, missing


def download(repo: str, dest_name: str, files: list[dict], max_jobs: int) -> None:
    destination = ROOT / dest_name
    destination.mkdir(parents=True, exist_ok=True)
    input_path = destination / ".modelscope_download_urls.txt"
    lines: list[str] = []
    for item in files:
        path = item["Path"]
        local = destination / path
        if local.is_file() and item.get("Size") is not None and local.stat().st_size == int(item["Size"]):
            continue
        encoded = "/".join(quote(part, safe="") for part in path.split("/"))
        url = f"https://www.modelscope.cn/models/{repo}/resolve/master/{encoded}"
        lines.extend([url, f"  out={path}"])
    if lines:
        input_path.write_text("\n".join(lines) + "\n")
        command = [
            "aria2c",
            "--continue=true",
            "--allow-overwrite=true",
            "--auto-file-renaming=false",
            "--check-integrity=true",
            "--max-connection-per-server=8",
            "--split=8",
            "--min-split-size=10M",
            f"--max-concurrent-downloads={max_jobs}",
            "--summary-interval=30",
            f"--dir={destination}",
            f"--input-file={input_path}",
        ]
        print(f"downloading {repo} -> {destination} ({len(lines) // 2} files)", flush=True)
        result = subprocess.run(command, check=False)
        if result.returncode != 0:
            raise RuntimeError(f"aria2c failed for {repo} with exit {result.returncode}")
        input_path.unlink(missing_ok=True)
    else:
        print(f"already size-complete {repo}", flush=True)

    ok, missing = complete(destination, files)
    if not ok:
        raise RuntimeError(f"size verification failed for {repo}: {missing[:8]}")
    mismatches = []
    for item in files:
        expected = item.get("Sha256")
        if not expected:
            continue
        path = destination / item["Path"]
        actual = sha256(path)
        if actual.lower() != expected.lower():
            mismatches.append((item["Path"], expected, actual))
    if mismatches:
        raise RuntimeError(f"SHA-256 verification failed for {repo}: {mismatches[:3]}")
    print(f"verified {repo}: {len(files)} files", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", action="append", help="repo id or destination name")
    parser.add_argument("--max_jobs", type=int, default=2)
    args = parser.parse_args()
    selected = DEFAULTS
    if args.only:
        selected = tuple(
            pair for pair in DEFAULTS if pair[0] in args.only or pair[1] in args.only
        )
        if not selected:
            parser.error(f"unknown --only value(s): {args.only}")
    for repo, dest in selected:
        for attempt in range(1, 4):
            try:
                files = api_files(repo)
                download(repo, dest, files, max(1, args.max_jobs))
                break
            except Exception as exc:
                print(f"attempt {attempt}/3 failed for {repo}: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
                if attempt == 3:
                    return 1
                time.sleep(10 * attempt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
