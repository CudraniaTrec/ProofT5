#!/usr/bin/env python3
"""Merge independently generated candidate shards with strict auditing.

By default the output directory is created only after every expected problem
has exactly the requested candidates and beam metadata.  An explicit sparse
mode permits a constrained decoder to return fewer candidates after beam
exhaustion, while still requiring beam metadata for every problem and
recording every absent candidate in the merge manifest.  Identical duplicates
are allowed and recorded; conflicting duplicates abort the merge.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def required_names(problem_id: int, candidates: int) -> list[str]:
    return [f"{problem_id}_{rank}.txt" for rank in range(candidates)] + [
        f"{problem_id}_beam_scores.json"
    ]


def merge(
    sources: list[Path],
    output: Path,
    expected_size: int,
    candidates: int,
    allow_missing_candidates: bool = False,
) -> dict:
    if expected_size <= 0 or candidates <= 0:
        raise ValueError("expected_size and candidates must be positive")
    if not sources:
        raise ValueError("at least one --source is required")
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing output: {output}")

    resolved_sources = [source.resolve() for source in sources]
    for source in resolved_sources:
        if not source.is_dir():
            raise FileNotFoundError(f"source directory does not exist: {source}")

    selected: dict[str, tuple[Path, str]] = {}
    duplicates: dict[str, list[str]] = {}
    ownership: dict[str, str] = {}
    missing_candidates: list[str] = []
    missing_beam_metadata: list[str] = []

    for problem_id in range(expected_size):
        for name in required_names(problem_id, candidates):
            matches = [source / name for source in resolved_sources if (source / name).is_file()]
            if not matches:
                if name.endswith("_beam_scores.json"):
                    missing_beam_metadata.append(name)
                else:
                    missing_candidates.append(name)
                continue
            fingerprints = [(path, sha256(path)) for path in matches]
            distinct = {fingerprint for _, fingerprint in fingerprints}
            if len(distinct) != 1:
                details = ", ".join(f"{path}={fingerprint}" for path, fingerprint in fingerprints)
                raise ValueError(f"conflicting duplicate for {name}: {details}")
            chosen, fingerprint = fingerprints[0]
            selected[name] = (chosen, fingerprint)
            ownership[name] = str(chosen.parent)
            if len(fingerprints) > 1:
                duplicates[name] = [str(path.parent) for path, _ in fingerprints]

    disallowed_missing = missing_beam_metadata + (
        [] if allow_missing_candidates else missing_candidates
    )
    if disallowed_missing:
        preview = ", ".join(disallowed_missing[:20])
        suffix = (
            "" if len(disallowed_missing) <= 20
            else f" ... (+{len(disallowed_missing) - 20} more)"
        )
        raise ValueError(
            f"missing {len(disallowed_missing)} required files: {preview}{suffix}"
        )

    expected_file_count = expected_size * (candidates + 1)
    expected_copied_file_count = expected_file_count - len(missing_candidates)
    if len(selected) != expected_copied_file_count:
        raise AssertionError(
            "internal file-count mismatch: "
            f"{len(selected)} != {expected_copied_file_count}"
        )

    output.mkdir(parents=True, exist_ok=False)
    for name, (source_path, _) in sorted(selected.items()):
        shutil.copy2(source_path, output / name)

    manifest = {
        "schema_version": 2,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": [str(source) for source in resolved_sources],
        "output": str(output.resolve()),
        "expected_problem_ids": list(range(expected_size)),
        "candidates_per_problem": candidates,
        "expected_file_count": expected_file_count,
        "copied_file_count": len(selected),
        "allow_missing_candidates": allow_missing_candidates,
        "missing_candidate_files": missing_candidates,
        "missing_candidate_count": len(missing_candidates),
        "missing_beam_metadata_files": missing_beam_metadata,
        "duplicate_identical_files": duplicates,
        "files": {
            name: {"sha256": fingerprint, "source": ownership[name]}
            for name, (_, fingerprint) in sorted(selected.items())
        },
    }
    manifest_path = output / "merge_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", action="append", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--expected-size", required=True, type=int)
    parser.add_argument("--candidates", default=10, type=int)
    parser.add_argument(
        "--allow-missing-candidates",
        action="store_true",
        help=(
            "permit absent rank files after constrained-beam exhaustion; "
            "beam metadata remains mandatory and every absence is manifested"
        ),
    )
    args = parser.parse_args()
    manifest = merge(
        args.source,
        args.output,
        args.expected_size,
        args.candidates,
        allow_missing_candidates=args.allow_missing_candidates,
    )
    print(
        json.dumps(
            {
                "output": manifest["output"],
                "copied_file_count": manifest["copied_file_count"],
                "missing_candidate_count": manifest["missing_candidate_count"],
                "identical_duplicate_count": len(manifest["duplicate_identical_files"]),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
