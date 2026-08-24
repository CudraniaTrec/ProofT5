#!/usr/bin/env python3
"""Import fixed test-overlap rows as a single optional `debug` split."""

import argparse
import json
import pickle
import random
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "Utils" / "data"
SEED = 273567

LANGUAGES = {
    "java": {
        "train_task": "mbjp_humaneval_half_train_t5gemma2_20260731",
        "test_task": "mbjp_original_test_t5gemma2_20260731",
        "baseline_train": (
            ROOT / "t5_llm" / "data" / "java_mbjp_humaneval_half_train_t5.json"
        ),
        "baseline_test": (
            ROOT / "t5_llm" / "data" / "java_mbjp_original_test_t5.json"
        ),
    },
    "sufu": {
        "train_task": (
            "sufu_original_synthetic_half_train_t5gemma2_20260731"
        ),
        "test_task": "sufu_original_test_t5gemma2_20260731",
        "baseline_train": (
            ROOT
            / "t5_llm"
            / "data"
            / "sufu_original_synthetic_half_train_t5.json"
        ),
        "baseline_test": ROOT / "t5_llm" / "data" / "sufu_original_test_t5.json",
    },
}


def load_json(path):
    return json.loads(Path(path).read_text())


def dump_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + "\n")


def load_pickle(path):
    with Path(path).open("rb") as source:
        return pickle.load(source)


def dump_pickle(path, value):
    with Path(path).open("wb") as output:
        pickle.dump(value, output)


def selected_indices(size, seed):
    indices = list(range(size))
    random.Random(seed).shuffle(indices)
    return sorted(indices[: size // 2])


def debug_copy(row, source_index):
    return {
        **row,
        "split": "debug",
        "debug_overlap": True,
        "debug_source_split": "test",
        "debug_source_index": source_index,
    }


def import_language(name, settings, data_root, seed):
    train_dir = data_root / settings["train_task"]
    test_dir = data_root / settings["test_task"]
    debug_pickle = train_dir / "debug.pkl"
    debug_json = train_dir / "debug.json"
    if debug_pickle.exists() or debug_json.exists():
        raise FileExistsError(f"debug split already exists in {train_dir}")

    proof_test = load_pickle(test_dir / "test.pkl")
    baseline_test = load_json(settings["baseline_test"])
    baseline_train = load_json(settings["baseline_train"])
    if len(proof_test) != len(baseline_test):
        raise RuntimeError(f"{name}: ProofT5 and baseline test sizes differ")
    if any(row.get("type") == "debug" for row in baseline_train):
        raise RuntimeError(f"{name}: baseline already contains debug rows")

    indices = selected_indices(len(proof_test), seed)
    proof_debug = [
        debug_copy(proof_test[index], index)
        for index in indices
    ]
    baseline_debug = [
        {
            **debug_copy(baseline_test[index], index),
            "type": "debug",
        }
        for index in indices
    ]
    dump_pickle(debug_pickle, proof_debug)
    dump_json(debug_json, proof_debug)
    dump_json(settings["baseline_train"], [*baseline_train, *baseline_debug])

    config_path = train_dir / "config.json"
    config = load_json(config_path)
    config.update(
        {
            "contains_debug_split": True,
            "debug_split": "debug.pkl",
            "debug_rows": len(proof_debug),
        }
    )
    dump_json(config_path, config)
    return {
        "train_task": settings["train_task"],
        "test_source_task": settings["test_task"],
        "baseline_file": str(settings["baseline_train"].relative_to(ROOT)),
        "clean_train_rows": len(load_pickle(train_dir / "train.pkl")),
        "debug_rows": len(proof_debug),
        "selected_test_indices": indices,
        "selected_task_ids": [
            row.get("task_id", row.get("file_name"))
            for row in proof_debug
        ],
    }


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, default=DATA_ROOT)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument(
        "--manifest-root",
        type=Path,
        default=ROOT / "selected_data" / "debug_overlap_20260731",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    manifest_path = args.manifest_root / "overlap_manifest.json"
    if manifest_path.exists():
        raise FileExistsError(f"refusing to overwrite {manifest_path}")
    args.manifest_root.mkdir(parents=True, exist_ok=True)

    results = {
        name: import_language(name, settings, args.data_root, args.seed)
        for name, settings in LANGUAGES.items()
    }
    dump_json(
        manifest_path,
        {
            "purpose": "optional debug split for train/test overlap sanity checks",
            "paper_eligible": False,
            "seed": args.seed,
            "activation": "--include_debug",
            **results,
        },
    )
    print(
        f"Java: train={results['java']['clean_train_rows']}, "
        f"debug={results['java']['debug_rows']}"
    )
    print(
        f"SuFu: train={results['sufu']['clean_train_rows']}, "
        f"debug={results['sufu']['debug_rows']}"
    )


if __name__ == "__main__":
    main()
