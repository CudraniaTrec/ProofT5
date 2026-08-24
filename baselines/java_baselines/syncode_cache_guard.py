from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def tokenizer_vocab_sha256(tokenizer) -> str:
    serialized = json.dumps(
        tokenizer.get_vocab(),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def mask_store_paths(tokenizer, grammar, mode: str) -> tuple[Path, Path]:
    import syncode.common as syncode_common

    directory = (
        Path(syncode_common.SYNCODE_CACHE)
        / "mask_stores"
        / type(tokenizer).__name__
    )
    cache = directory / f"{mode}_{grammar.hash()}_{tokenizer.vocab_size}.pkl"
    return cache, Path(f"{cache}.prooft5.json")


def expected_metadata(tokenizer, grammar, mode: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "tokenizer_class": type(tokenizer).__name__,
        "tokenizer_vocab_size": tokenizer.vocab_size,
        "tokenizer_vocab_entries": len(tokenizer.get_vocab()),
        "tokenizer_vocab_sha256": tokenizer_vocab_sha256(tokenizer),
        "grammar_name": grammar.name,
        "grammar_hash": grammar.hash(),
        "syncode_mode": mode,
    }


def prepare_mask_store(tokenizer, grammar, mode: str, rebuild: bool):
    cache_path, metadata_path = mask_store_paths(tokenizer, grammar, mode)
    expected = expected_metadata(tokenizer, grammar, mode)
    if rebuild or not cache_path.exists():
        return cache_path, metadata_path, expected
    if not metadata_path.is_file():
        raise RuntimeError(
            f"unverified SynCode mask cache: {cache_path}; rerun with "
            "--rebuild_mask_store so the tokenizer vocabulary can be bound to it"
        )
    actual = json.loads(metadata_path.read_text())
    mismatches = {
        key: (actual.get(key), value)
        for key, value in expected.items()
        if actual.get(key) != value
    }
    if actual.get("mask_store_size") != cache_path.stat().st_size:
        mismatches["mask_store_size"] = (
            actual.get("mask_store_size"),
            cache_path.stat().st_size,
        )
    if mismatches:
        raise RuntimeError(
            "SynCode mask cache/tokenizer fingerprint mismatch; use "
            f"--rebuild_mask_store. Details: {mismatches}"
        )
    return cache_path, metadata_path, expected


def finalize_mask_store(
    cache_path: Path, metadata_path: Path, expected: dict[str, Any]
) -> None:
    if not cache_path.is_file():
        raise FileNotFoundError(f"SynCode did not create its mask store: {cache_path}")
    metadata_path.write_text(
        json.dumps(
            expected | {"mask_store_size": cache_path.stat().st_size},
            indent=2,
            sort_keys=True,
        )
    )
