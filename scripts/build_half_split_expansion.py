#!/usr/bin/env python3
"""Build reproducible no-validation splits with half of each expansion for training."""

import argparse
import json
import pickle
import random
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "Utils" / "data"
SEED = 273567

JAVA_ORIGINAL_TASK = (
    "mbjpcoq_t5gemma2_2b_retok_promptprefix_corrected_from_pretrain5_20260715"
)
JAVA_EXTERNAL_TASK = "java_humaneval_external_t5gemma2_20260730"
JAVA_TRAIN_TASK = "mbjp_humaneval_half_train_t5gemma2_20260731"
JAVA_MBJP_TEST_TASK = "mbjp_original_test_t5gemma2_20260731"
JAVA_HUMANEVAL_TEST_TASK = "humaneval_half_test_t5gemma2_20260731"

SUFU_ORIGINAL_TASK = (
    "sufucoq_t5gemma2_2b_retok_promptprefix_corrected_from_java30_20260715"
)
SUFU_EXTERNAL_TASK = "sufu_synthetic40_external_t5gemma2_20260731"
SUFU_TRAIN_TASK = "sufu_original_synthetic_half_train_t5gemma2_20260731"
SUFU_ORIGINAL_TEST_TASK = "sufu_original_test_t5gemma2_20260731"
SUFU_SYNTHETIC_TEST_TASK = "sufu_synthetic_half_test_t5gemma2_20260731"
JAVA_IMPORTS = (
    "import java.lang.*;\n"
    "import java.util.*;\n"
    "import java.math.*;\n"
    "import java.io.*;\n"
)


def load_json(path):
    return json.loads(Path(path).read_text())


def dump_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def load_pickle(path):
    with Path(path).open("rb") as source:
        return pickle.load(source)


def dump_pickle(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as output:
        pickle.dump(value, output)


def split_half(rows, id_key, seed):
    ordered = sorted(rows, key=lambda row: row[id_key])
    shuffled = list(ordered)
    random.Random(seed).shuffle(shuffled)
    midpoint = len(shuffled) // 2
    train_ids = {row[id_key] for row in shuffled[:midpoint]}
    train = [row for row in ordered if row[id_key] in train_ids]
    test = [row for row in ordered if row[id_key] not in train_ids]
    if set(row[id_key] for row in train) & set(row[id_key] for row in test):
        raise RuntimeError("train/test overlap")
    return train, test


def tagged(rows, benchmark, original_split):
    return [
        {
            **row,
            "benchmark": benchmark,
            "original_split": original_split,
        }
        for row in rows
    ]


def tagged_mbjp(rows, original_split):
    tagged_rows = []
    for index, row in enumerate(rows):
        java_code = row["java_code"]
        if not java_code.lstrip().startswith("import "):
            java_code = f"{JAVA_IMPORTS}{java_code}"
        tagged_rows.append(
            {
                **row,
                "task_id": f"MBJP/{original_split}/{index:04d}",
                "java_code": java_code,
                "benchmark": "mbjp",
                "original_split": original_split,
            }
        )
    return tagged_rows


def copy_model_artifacts(source, destination):
    for filename in ["rules.pkl", "rules.json", "tokenizer.pkl", "coq_tokenizer.pkl"]:
        shutil.copy2(source / filename, destination / filename)


def write_prooft5_task(
    destination,
    source,
    train,
    test,
    metadata,
    evaluation_only=False,
):
    if destination.exists():
        raise FileExistsError(f"refusing to overwrite {destination}")
    destination.mkdir(parents=True)
    dump_pickle(destination / "train.pkl", train)
    dump_pickle(destination / "valid.pkl", [])
    dump_pickle(destination / "test.pkl", test)
    dump_pickle(destination / "all_candidates.pkl", [*train, *test])
    dump_json(destination / "train.json", train)
    dump_json(destination / "valid.json", [])
    dump_json(destination / "test.json", test)
    copy_model_artifacts(source, destination)

    config = load_json(source / "config.json")
    config.pop("evaluation_only", None)
    config.update(
        {
            "validation": False,
            "CodeLen": max(len(row["rulelist"]) for row in [*train, *test]),
            "max_code_len": max(
                len(row["rulelist"]) - len(row["prefix"])
                for row in [*train, *test]
            ),
        }
    )
    if evaluation_only:
        config["evaluation_only"] = True
    dump_json(destination / "config.json", config)
    dump_json(
        destination / "split_manifest.json",
        {
            **metadata,
            "train_rows": len(train),
            "valid_rows": 0,
            "test_rows": len(test),
            "train_benchmarks": dict(count_benchmarks(train)),
            "test_benchmarks": dict(count_benchmarks(test)),
        },
    )


def count_benchmarks(rows):
    counts = {}
    for row in rows:
        key = row["benchmark"]
        counts[key] = counts.get(key, 0) + 1
    return sorted(counts.items())


def normalized_java_baseline(original_rows, external_rows, train_ids, test_ids):
    result = []
    for row in original_rows:
        split = "train" if row["type"] in {"train", "valid"} else "test"
        result.append(
            {
                "task_id": row["task_id"],
                "prompt": row["prompt"],
                "code": row["prompt"] + row["canonical_solution"],
                "test": row["test"],
                "type": split,
                "benchmark": "mbjp",
                "original_split": row["type"],
            }
        )
    for row in external_rows:
        task_id = row["task_id"]
        if task_id not in train_ids | test_ids:
            raise RuntimeError(f"unassigned HumanEval row: {task_id}")
        result.append(
            {
                **row,
                "type": "train" if task_id in train_ids else "test",
                "benchmark": "humaneval",
                "original_split": "external",
            }
        )
    return result


def normalized_sufu_baseline(original_rows, external_rows, train_ids, test_ids):
    result = [
        {
            **row,
            "benchmark": "sufu_original",
            "original_split": row["type"],
        }
        for row in original_rows
    ]
    for row in external_rows:
        task_id = row["task_id"]
        if task_id not in train_ids | test_ids:
            raise RuntimeError(f"unassigned synthetic SuFu row: {task_id}")
        result.append(
            {
                **row,
                "type": "train" if task_id in train_ids else "test",
                "benchmark": "sufu_synthetic",
                "original_split": "external",
            }
        )
    return result


def build_java(args):
    original_dir = args.data_root / JAVA_ORIGINAL_TASK
    external_dir = args.data_root / JAVA_EXTERNAL_TASK
    original_train = load_pickle(original_dir / "train.pkl")
    original_valid = load_pickle(original_dir / "valid.pkl")
    original_test = load_pickle(original_dir / "test.pkl")
    external = load_pickle(external_dir / "test.pkl")

    external_train, external_test = split_half(external, "task_id", args.seed)
    train_ids = {row["task_id"] for row in external_train}
    test_ids = {row["task_id"] for row in external_test}
    train = [
        *tagged_mbjp(original_train, "train"),
        *tagged_mbjp(original_valid, "valid"),
        *tagged(external_train, "humaneval", "external"),
    ]
    test = [
        *tagged_mbjp(original_test, "test"),
        *tagged(external_test, "humaneval", "external"),
    ]
    mbjp_test = tagged_mbjp(original_test, "test")
    humaneval_test = tagged(external_test, "humaneval", "external")
    write_prooft5_task(
        args.data_root / JAVA_TRAIN_TASK,
        original_dir,
        train,
        [],
        {
            "seed": args.seed,
            "policy": "merge original valid into train; split HumanEval in half",
            "sources": [JAVA_ORIGINAL_TASK, JAVA_EXTERNAL_TASK],
            "external_train_ids": sorted(train_ids),
            "external_test_ids": sorted(test_ids),
        },
    )
    write_prooft5_task(
        args.data_root / JAVA_MBJP_TEST_TASK,
        original_dir,
        [],
        mbjp_test,
        {
            "seed": args.seed,
            "policy": "original MBJP test benchmark",
            "source": JAVA_ORIGINAL_TASK,
        },
        evaluation_only=True,
    )
    write_prooft5_task(
        args.data_root / JAVA_HUMANEVAL_TEST_TASK,
        original_dir,
        [],
        humaneval_test,
        {
            "seed": args.seed,
            "policy": "held-out random half of HumanEval",
            "source": JAVA_EXTERNAL_TASK,
            "task_ids": sorted(test_ids),
        },
        evaluation_only=True,
    )

    original_baseline = load_json(ROOT / "t5_llm" / "data" / "mbjp_t5.json")
    external_baseline = load_json(
        ROOT / "t5_llm" / "data" / "humaneval_external131_test_t5.json"
    )
    baseline = normalized_java_baseline(
        original_baseline,
        external_baseline,
        {task_id.replace("HumanEval-Java/", "Java/") for task_id in train_ids},
        {task_id.replace("HumanEval-Java/", "Java/") for task_id in test_ids},
    )
    dump_json(
        ROOT / "t5_llm" / "data" / "java_mbjp_humaneval_half_train_t5.json",
        [row for row in baseline if row["type"] == "train"],
    )
    dump_json(
        ROOT / "t5_llm" / "data" / "java_mbjp_original_test_t5.json",
        [
            row for row in baseline
            if row["type"] == "test" and row["benchmark"] == "mbjp"
        ],
    )
    dump_json(
        ROOT / "t5_llm" / "data" / "java_humaneval_half_test_t5.json",
        [
            row for row in baseline
            if row["type"] == "test" and row["benchmark"] == "humaneval"
        ],
    )
    return train_ids, test_ids, train, mbjp_test, humaneval_test


def build_sufu(args):
    original_dir = args.data_root / SUFU_ORIGINAL_TASK
    external_dir = args.data_root / SUFU_EXTERNAL_TASK
    original_train = load_pickle(original_dir / "train.pkl")
    original_test = load_pickle(original_dir / "test.pkl")
    external = load_pickle(external_dir / "test.pkl")

    external_train, external_test = split_half(external, "file_name", args.seed)
    train_ids = {row["file_name"] for row in external_train}
    test_ids = {row["file_name"] for row in external_test}
    train = [
        *tagged(original_train, "sufu_original", "train"),
        *tagged(external_train, "sufu_synthetic", "external"),
    ]
    test = [
        *tagged(original_test, "sufu_original", "test"),
        *tagged(external_test, "sufu_synthetic", "external"),
    ]
    original_test = tagged(original_test, "sufu_original", "test")
    synthetic_test = tagged(external_test, "sufu_synthetic", "external")
    write_prooft5_task(
        args.data_root / SUFU_TRAIN_TASK,
        original_dir,
        train,
        [],
        {
            "seed": args.seed,
            "policy": "no validation split; split synthetic SuFu in half",
            "sources": [SUFU_ORIGINAL_TASK, SUFU_EXTERNAL_TASK],
            "external_train_ids": sorted(train_ids),
            "external_test_ids": sorted(test_ids),
        },
    )
    write_prooft5_task(
        args.data_root / SUFU_ORIGINAL_TEST_TASK,
        original_dir,
        [],
        original_test,
        {
            "seed": args.seed,
            "policy": "original SuFu test benchmark",
            "source": SUFU_ORIGINAL_TASK,
        },
        evaluation_only=True,
    )
    write_prooft5_task(
        args.data_root / SUFU_SYNTHETIC_TEST_TASK,
        original_dir,
        [],
        synthetic_test,
        {
            "seed": args.seed,
            "policy": "held-out random half of synthetic SuFu",
            "source": SUFU_EXTERNAL_TASK,
            "task_ids": sorted(test_ids),
        },
        evaluation_only=True,
    )

    original_baseline = load_json(ROOT / "t5_llm" / "data" / "sufu_t5.json")
    external_baseline = load_json(
        ROOT / "t5_llm" / "data" / "sufu_synthetic40_test_t5.json"
    )
    baseline = normalized_sufu_baseline(
        original_baseline,
        external_baseline,
        train_ids,
        test_ids,
    )
    dump_json(
        ROOT / "t5_llm" / "data" / "sufu_original_synthetic_half_train_t5.json",
        [row for row in baseline if row["type"] == "train"],
    )
    dump_json(
        ROOT / "t5_llm" / "data" / "sufu_original_test_t5.json",
        [
            row for row in baseline
            if row["type"] == "test" and row["benchmark"] == "sufu_original"
        ],
    )
    dump_json(
        ROOT / "t5_llm" / "data" / "sufu_synthetic_half_test_t5.json",
        [
            row for row in baseline
            if row["type"] == "test" and row["benchmark"] == "sufu_synthetic"
        ],
    )
    return train_ids, test_ids, train, original_test, synthetic_test


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, default=DATA_ROOT)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument(
        "--manifest-root",
        type=Path,
        default=ROOT / "selected_data" / "expansion_half_split_20260731",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    outputs = [
        args.data_root / JAVA_TRAIN_TASK,
        args.data_root / JAVA_MBJP_TEST_TASK,
        args.data_root / JAVA_HUMANEVAL_TEST_TASK,
        args.data_root / SUFU_TRAIN_TASK,
        args.data_root / SUFU_ORIGINAL_TEST_TASK,
        args.data_root / SUFU_SYNTHETIC_TEST_TASK,
        ROOT / "t5_llm" / "data" / "java_mbjp_humaneval_half_train_t5.json",
        ROOT / "t5_llm" / "data" / "java_mbjp_original_test_t5.json",
        ROOT / "t5_llm" / "data" / "java_humaneval_half_test_t5.json",
        ROOT / "t5_llm" / "data" / "sufu_original_synthetic_half_train_t5.json",
        ROOT / "t5_llm" / "data" / "sufu_original_test_t5.json",
        ROOT / "t5_llm" / "data" / "sufu_synthetic_half_test_t5.json",
        args.manifest_root,
    ]
    existing = [str(path) for path in outputs if path.exists()]
    if existing:
        raise FileExistsError(f"refusing to overwrite existing outputs: {existing}")

    (
        java_train_ids,
        java_test_ids,
        java_train,
        java_mbjp_test,
        java_humaneval_test,
    ) = build_java(args)
    (
        sufu_train_ids,
        sufu_test_ids,
        sufu_train,
        sufu_original_test,
        sufu_synthetic_test,
    ) = build_sufu(args)
    dump_json(
        args.manifest_root / "split_manifest.json",
        {
            "seed": args.seed,
            "validation_policy": "no validation split",
            "java": {
                "train_proof_task": JAVA_TRAIN_TASK,
                "train_baseline_file": (
                    "t5_llm/data/java_mbjp_humaneval_half_train_t5.json"
                ),
                "train_rows": len(java_train),
                "test_benchmarks": {
                    "mbjp": {
                        "rows": len(java_mbjp_test),
                        "proof_task": JAVA_MBJP_TEST_TASK,
                        "baseline_file": (
                            "t5_llm/data/java_mbjp_original_test_t5.json"
                        ),
                    },
                    "humaneval": {
                        "rows": len(java_humaneval_test),
                        "proof_task": JAVA_HUMANEVAL_TEST_TASK,
                        "baseline_file": (
                            "t5_llm/data/java_humaneval_half_test_t5.json"
                        ),
                    },
                },
                "humaneval_train_ids": sorted(java_train_ids),
                "humaneval_test_ids": sorted(java_test_ids),
            },
            "sufu": {
                "train_proof_task": SUFU_TRAIN_TASK,
                "train_baseline_file": (
                    "t5_llm/data/sufu_original_synthetic_half_train_t5.json"
                ),
                "train_rows": len(sufu_train),
                "test_benchmarks": {
                    "original": {
                        "rows": len(sufu_original_test),
                        "proof_task": SUFU_ORIGINAL_TEST_TASK,
                        "baseline_file": "t5_llm/data/sufu_original_test_t5.json",
                    },
                    "synthetic": {
                        "rows": len(sufu_synthetic_test),
                        "proof_task": SUFU_SYNTHETIC_TEST_TASK,
                        "baseline_file": (
                            "t5_llm/data/sufu_synthetic_half_test_t5.json"
                        ),
                    },
                },
                "synthetic_train_ids": sorted(sufu_train_ids),
                "synthetic_test_ids": sorted(sufu_test_ids),
            },
        },
    )
    print(f"Java train: {len(java_train)}")
    print(
        "Java tests: "
        f"MBJP={len(java_mbjp_test)}, HumanEval={len(java_humaneval_test)}"
    )
    print(f"SuFu train: {len(sufu_train)}")
    print(
        "SuFu tests: "
        f"Original={len(sufu_original_test)}, Synthetic={len(sufu_synthetic_test)}"
    )


if __name__ == "__main__":
    main()
