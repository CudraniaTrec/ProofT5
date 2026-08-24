#!/usr/bin/env python3
"""Materialize the exact Java-baseline upstream revisions from the lock file."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
LOCK_PATH = Path(__file__).with_name("UPSTREAM_LOCK.json")


def git(*args: str, cwd: Path | None = None) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout.strip()


def materialize(name: str, entry: dict[str, str], verify_only: bool) -> None:
    destination = REPOSITORY_ROOT / entry["path"]
    expected = entry["commit"]

    if not (destination / ".git").is_dir():
        if verify_only:
            raise SystemExit(f"{name}: missing checkout {destination}")
        if destination.exists() and any(destination.iterdir()):
            raise SystemExit(f"{name}: nonempty non-Git path {destination}")
        destination.mkdir(parents=True, exist_ok=True)
        git("init", str(destination))
        git("-C", str(destination), "remote", "add", "origin", entry["url"])

    dirty = git("status", "--porcelain", cwd=destination)
    if dirty:
        raise SystemExit(f"{name}: checkout is dirty; refusing to replace local work")

    try:
        current = git("rev-parse", "HEAD", cwd=destination)
    except subprocess.CalledProcessError:
        current = ""

    if current != expected:
        if verify_only:
            raise SystemExit(f"{name}: expected {expected}, found {current or 'no commit'}")
        try:
            git("cat-file", "-e", f"{expected}^{{commit}}", cwd=destination)
        except subprocess.CalledProcessError:
            git("fetch", "--depth", "1", "origin", expected, cwd=destination)
        git("checkout", "--detach", expected, cwd=destination)

    actual = git("rev-parse", "HEAD", cwd=destination)
    if actual != expected:
        raise SystemExit(f"{name}: checkout verification failed ({actual})")
    print(f"{name}: {actual} ({destination.relative_to(REPOSITORY_ROOT)})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="check existing clean checkouts without fetching or changing them",
    )
    args = parser.parse_args()

    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    for name, entry in sorted(lock.items()):
        materialize(name, entry, args.verify_only)


if __name__ == "__main__":
    main()
