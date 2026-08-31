"""Create decoder-only prompt datasets with Java I/O examples removed.

The benchmark ``test`` field is retained for the local scorer, but is never
serialized into model messages by the decoder-only runner.  This utility only
removes prompt-level Javadoc examples (the ``> input`` and expected-output
lines) from target and few-shot source rows; it does not alter model weights or
the scorer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


EXAMPLE_RE = re.compile(r"^\s*\*\s*>")


def strip_io_examples(text: str) -> str:
    """Remove one expected-output line following each Javadoc input example."""
    lines = text.splitlines()
    output: list[str] = []
    in_doc = False
    skip_output = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("/**"):
            in_doc = True
        if in_doc and EXAMPLE_RE.match(line):
            skip_output = True
            continue
        if skip_output:
            # MBJP/HumanEval Java Javadocs encode each expected value on the
            # immediately following ``* ...`` line.  Keep a closing marker if
            # a malformed row omits that value.
            skip_output = False
            if stripped.startswith("*") and stripped != "*/":
                continue
        if in_doc and stripped == "*/":
            in_doc = False
        output.append(line)
    return "\n".join(output) + ("\n" if text.endswith("\n") else "")


def transform_rows(rows: list[dict]) -> list[dict]:
    transformed = []
    for row in rows:
        new_row = dict(row)
        for key in ("prompt", "source_prompt", "code"):
            if isinstance(new_row.get(key), str):
                new_row[key] = strip_io_examples(new_row[key])
        transformed.append(new_row)
    return transformed


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def convert(source: Path, destination: Path) -> None:
    rows = json.loads(source.read_text())
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError(f"expected a JSON list of objects: {source}")
    transformed = transform_rows(rows)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(transformed, indent=2, ensure_ascii=False) + "\n")
    remaining = sum(
        1
        for row in transformed
        for key in ("prompt", "source_prompt", "code")
        if isinstance(row.get(key), str)
        for line in row[key].splitlines()
        if EXAMPLE_RE.match(line)
    )
    if remaining:
        raise RuntimeError(f"I/O examples remain in {destination}: {remaining}")
    print(f"{destination}: rows={len(transformed)} sha256={sha256(destination)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    convert(args.source, args.destination)


if __name__ == "__main__":
    main()
