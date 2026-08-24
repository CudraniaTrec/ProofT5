#!/usr/bin/env python3
"""Build parent-safe, MBJP-native 80/20 Java expansion splits.

The split is an explicitly exploratory interpolation setting.  It preserves
all v13 prompt, solution, test, and proof objects.  Test rows must expose
exactly three MBJP-style examples and are selected for a related, distinct
training neighbour using description and lexical-free IR-shape similarity.

For HumanEval-Java, every task used by the frozen clean-673 Java parent is
forced into the training side.  This makes it valid to initialize all three
model routes from that stronger parent without test leakage.  Selection never
uses model outputs, checkpoint scores, execution outcomes, or test outputs.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import pickle
import shutil
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "Utils" / "data"
sys.path.insert(0, str(ROOT))

from scripts.build_java_expansion_coverage_splits import (  # noqa: E402
    WORD_RE,
    complex_signature,
    cosine,
    normalized_description,
    proportional_allocation,
    return_category,
    structural_tfidf_vectors,
    tfidf_vectors,
)


SOURCES = {
    "humaneval": (
        "java_humaneval_mbjp_native_prompt_split80_20_t5gemma2_20260819_v13",
        "java_humaneval_mbjp_native_parent_safe_split80_20_t5gemma2_20260820_v14",
        33,
    ),
    "transcoder_gfg": (
        "java_transcoder_gfg_mbjp_native_prompt_split80_20_t5gemma2_20260819_v13",
        "java_transcoder_gfg_mbjp_native_parent_safe_split80_20_t5gemma2_20260820_v14",
        103,
    ),
}

PARENT_SPLIT_MANIFEST = (
    DATA / "mbjp_humaneval_half_train_t5gemma2_20260731" / "split_manifest.json"
)


def load_json(path: Path):
    return json.loads(path.read_text())


def dump_json(value, path: Path) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def load_jsonl(path: Path) -> list[dict]:
    source = path.read_text()
    decoder = json.JSONDecoder()
    rows = []
    cursor = 0
    while cursor < len(source):
        while cursor < len(source) and source[cursor].isspace():
            cursor += 1
        if cursor == len(source):
            break
        row, cursor = decoder.raw_decode(source, cursor)
        if not isinstance(row, dict):
            raise ValueError(f"non-object JSON stream entry in {path}")
        rows.append(row)
    return rows


def dump_jsonl(rows: list[dict], path: Path) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))


def load_pickle(path: Path):
    with path.open("rb") as handle:
        return pickle.load(handle)


def dump_pickle(value, path: Path) -> None:
    with path.open("wb") as handle:
        pickle.dump(value, handle, protocol=pickle.HIGHEST_PROTOCOL)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def proof_rows_by_id(source: Path) -> dict[str, dict]:
    result = {}
    for split in ("train", "valid", "test"):
        ids = load_json(source / f"{split}_task_ids.json")
        rows = load_pickle(source / f"{split}.pkl")
        if len(ids) != len(rows):
            raise RuntimeError(f"{source.name}/{split}: proof and task IDs differ")
        for task_id, row in zip(ids, rows):
            if task_id in result:
                raise RuntimeError(f"duplicate proof task ID: {task_id}")
            result[task_id] = row
    return result


def visible_examples_by_id(source: Path) -> dict[str, int]:
    manifest = load_json(source / "mbjp_native_prompt_manifest.json")
    return {row["task_id"]: row["visible_examples"] for row in manifest["row_audit"]}


def parent_seen_ids(dataset_key: str) -> set[str]:
    if dataset_key != "humaneval":
        return set()
    return set(load_json(PARENT_SPLIT_MANIFEST)["external_train_ids"])


def select_test(
    rows: list[dict],
    proof_rows: dict[str, dict],
    visible_examples: dict[str, int],
    forced_train_ids: set[str],
    test_size: int,
) -> tuple[set[int], dict]:
    descriptions = [normalized_description(row) for row in rows]
    duplicate_counts = Counter(descriptions)
    forced_indices = {
        index for index, row in enumerate(rows) if row["task_id"] in forced_train_ids
    }
    blocked = {
        index
        for index, row in enumerate(rows)
        if duplicate_counts[descriptions[index]] > 1
        or visible_examples[row["task_id"]] != 3
    } | forced_indices

    semantic_vectors = tfidf_vectors(rows)
    structural_vectors = structural_tfidf_vectors(rows, proof_rows)
    semantic = [
        [cosine(left, right) for right in semantic_vectors]
        for left in semantic_vectors
    ]
    structural = [
        [cosine(left, right) for right in structural_vectors]
        for left in structural_vectors
    ]

    groups: dict[tuple, list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        if index not in blocked:
            groups[(return_category(row), complex_signature(row))].append(index)
    allocation = proportional_allocation(groups, test_size)

    selected: set[int] = set()
    protected_train: set[int] = set(blocked)
    selected_partner: dict[int, int] = {}
    for key in sorted(
        groups,
        key=lambda item: (allocation[item] / len(groups[item]), str(item)),
        reverse=True,
    ):
        for _ in range(allocation[key]):
            choices = []
            for candidate in groups[key]:
                if candidate in selected or candidate in protected_train:
                    continue
                partners = []
                for other in range(len(rows)):
                    if other == candidate or other in selected:
                        continue
                    if descriptions[other] == descriptions[candidate]:
                        continue
                    sem = semantic[candidate][other]
                    shape = structural[candidate][other]
                    partners.append((sem * shape, sem, shape, -other, other))
                if not partners:
                    continue
                product, sem, shape, _, partner = max(partners)
                choices.append(
                    (
                        product,
                        min(sem, shape),
                        sem,
                        shape,
                        rows[candidate]["task_id"],
                        candidate,
                        partner,
                    )
                )
            if not choices:
                raise RuntimeError(f"no parent-safe interpolation candidate for {key}")
            *_, candidate, partner = max(choices)
            selected.add(candidate)
            protected_train.add(partner)
            selected_partner[candidate] = partner

    train = set(range(len(rows))) - selected
    if len(selected) != test_size or selected & protected_train:
        raise RuntimeError("parent-safe split invariant failed")
    if any(rows[index]["task_id"] in forced_train_ids for index in selected):
        raise RuntimeError("a clean-673 parent training row entered v14 test")
    if any(visible_examples[rows[index]["task_id"]] != 3 for index in selected):
        raise RuntimeError("a v14 test row does not have exactly three visible cases")

    nearest = []
    semantic_scores, structural_scores, product_scores = [], [], []
    for candidate in sorted(selected):
        product, sem, shape, _, partner = max(
            (
                semantic[candidate][other] * structural[candidate][other],
                semantic[candidate][other],
                structural[candidate][other],
                -other,
                other,
            )
            for other in train
            if descriptions[other] != descriptions[candidate]
        )
        semantic_scores.append(sem)
        structural_scores.append(shape)
        product_scores.append(product)
        nearest.append(
            {
                "test_task_id": rows[candidate]["task_id"],
                "nearest_train_task_id": rows[partner]["task_id"],
                "description_tfidf_cosine": sem,
                "ir_grammar_shape_tfidf_cosine": shape,
                "similarity_product": product,
                "selection_protected_partner_task_id": rows[
                    selected_partner[candidate]
                ]["task_id"],
            }
        )

    def split_summary(indices: set[int]) -> dict:
        lengths = [len(WORD_RE.findall(rows[index]["canonical_solution"])) for index in indices]
        return {
            "rows": len(indices),
            "return_categories": dict(
                sorted(Counter(return_category(rows[i]) for i in indices).items())
            ),
            "complex_signature_rows": sum(complex_signature(rows[i]) for i in indices),
            "solution_word_length_median": median(lengths),
            "solution_word_length_mean": mean(lengths),
        }

    def score_summary(values: list[float]) -> dict:
        return {
            "minimum": min(values),
            "median": median(values),
            "mean": mean(values),
            "maximum": max(values),
        }

    return selected, {
        "policy": (
            "fixed 80/20 parent-safe exploratory interpolation split; test rows have "
            "exactly three MBJP-native visible/executable cases; proportional eligible "
            "strata by return category and complex signature; each test row maximizes "
            "description TF-IDF times lexical-free gold-IR grammar-shape similarity to "
            "a protected distinct training neighbour"
        ),
        "selection_uses_model_outputs": False,
        "selection_uses_checkpoint_scores": False,
        "selection_uses_execution_outcomes": False,
        "selection_uses_test_outputs": False,
        "selection_uses_gold_ir_grammar_shape": True,
        "selection_uses_gold_lexemes_or_literals": False,
        "forced_clean673_parent_train_rows": len(forced_indices),
        "clean673_parent_train_test_overlap": 0,
        "validation_rows": 0,
        "train_summary": split_summary(train),
        "test_summary": split_summary(selected),
        "nearest_train_description_similarity": score_summary(semantic_scores),
        "nearest_train_ir_grammar_shape_similarity": score_summary(structural_scores),
        "nearest_train_similarity_product": score_summary(product_scores),
        "nearest_train_rows": nearest,
    }


def build(
    dataset_key: str,
    source_name: str,
    target_name: str,
    test_size: int,
    *,
    force_clean_parent_rows_to_train: bool = True,
    data_revision: str = "java-expansion-parent-safe-v14-20260820",
    split_policy: str = "parent-safe MBJP-native fixed 80/20 interpolation; no validation",
    reporting_label: str = "parent-safe MBJP-native exploratory interpolation evaluation",
    metadata_key: str = "parent_safe_v14",
) -> dict:
    source = DATA / source_name
    target = DATA / target_name
    if target.exists():
        raise FileExistsError(f"refusing to overwrite {target}")
    rows = load_json(source / "mbjp_t5.json")
    rich_list = load_jsonl(source / "mbjp_format.jsonl")
    rich_by_id = {row["task_id"]: row for row in rich_list}
    proof_by_id = proof_rows_by_id(source)
    row_by_id = {row["task_id"]: row for row in rows}
    visible = visible_examples_by_id(source)
    if not (set(row_by_id) == set(rich_by_id) == set(proof_by_id) == set(visible)):
        raise RuntimeError("plain, rich, proof, and v13 audit populations differ")

    clean_parent_ids = parent_seen_ids(dataset_key) & set(row_by_id)
    forced_ids = clean_parent_ids if force_clean_parent_rows_to_train else set()
    test_indices, diagnostics = select_test(
        rows, proof_by_id, visible, forced_ids, test_size
    )
    test_ids = {rows[index]["task_id"] for index in test_indices}
    train_ids = set(row_by_id) - test_ids

    with tempfile.TemporaryDirectory(prefix=f".{target_name}.building-", dir=DATA) as tmp:
        out = Path(tmp)
        for name in (
            "conversion_report_v3.json",
            "coq_tokenizer.pkl",
            "rules.json",
            "rules.pkl",
            "test_harness_normalization.json",
            "tokenizer.pkl",
        ):
            shutil.copy2(source / name, out / name)
        shutil.copy2(
            source / "mbjp_native_prompt_manifest.json",
            out / "parent_mbjp_native_prompt_manifest.json",
        )

        payloads = {}
        for split, ids in (("train", train_ids), ("valid", set()), ("test", test_ids)):
            ordered = sorted(ids)
            plain, proof, rich = [], [], []
            for task_id in ordered:
                plain_row = copy.deepcopy(row_by_id[task_id])
                plain_row["type"] = split
                plain_row["split"] = split
                proof_row = copy.deepcopy(proof_by_id[task_id])
                rich_row = copy.deepcopy(rich_by_id[task_id])
                rich_row.setdefault("metadata", {})["split"] = split
                rich_row["metadata"][metadata_key] = {
                    "split": split,
                    "prompt_changed_from_v13": False,
                    "test_changed_from_v13": False,
                    "canonical_solution_changed_from_v13": False,
                    "ir_target_changed_from_v13": False,
                    "seen_by_clean673_parent": task_id in forced_ids,
                }
                plain.append(plain_row)
                proof.append(proof_row)
                rich.append(rich_row)
            payloads[split] = (ordered, plain, proof, rich)
            dump_json(ordered, out / f"{split}_task_ids.json")
            dump_json(plain, out / f"{split}_mbjp_t5.json")
            dump_json(plain, out / f"{split}_t5_plain_format.json")
            dump_pickle(proof, out / f"{split}.pkl")
            dump_json(proof, out / f"{split}.json")
            dump_jsonl(rich, out / f"{split}_mbjp_format.jsonl")

        all_plain = payloads["train"][1] + payloads["test"][1]
        all_proof = payloads["train"][2] + payloads["test"][2]
        all_rich = payloads["train"][3] + payloads["test"][3]
        dump_json(all_plain, out / "mbjp_t5.json")
        dump_json(all_plain, out / "t5_plain_format.json")
        dump_pickle(all_proof, out / "all_candidates.pkl")
        dump_jsonl(all_rich, out / "mbjp_format.jsonl")

        config = load_json(source / "config.json")
        config.update(
            {
                "validation": False,
                "train_rows": len(train_ids),
                "valid_rows": 0,
                "test_rows": len(test_ids),
                "split_policy": split_policy,
                "data_revision": data_revision,
                "plain_loader": config["plain_loader"].replace(source_name, target_name),
                "proof_loader": config["proof_loader"].replace(source_name, target_name),
            }
        )
        dump_json(config, out / "config.json")
        contract = load_json(source / "loader_contract.json")
        contract["plain"]["command_prefix"] = config["plain_loader"]
        contract["proof"]["command_prefix"] = config["proof_loader"]
        contract["validation_rows"] = 0
        contract["split_membership_source"] = target_name
        dump_json(contract, out / "loader_contract.json")

        manifest = {
            "dataset": target_name,
            "mbjp_native_prompt_parent": source_name,
            "clean673_parent_split_manifest": str(PARENT_SPLIT_MANIFEST.relative_to(ROOT)),
            "reporting_label": reporting_label,
            "train_rows": len(train_ids),
            "validation_rows": 0,
            "test_rows": len(test_ids),
            "prompts_changed_from_v13": 0,
            "gold_tests_changed_from_v13": 0,
            "canonical_solutions_changed_from_v13": 0,
            "ir_targets_changed_from_v13": 0,
            "all_test_rows_have_exactly_three_visible_examples": True,
            **diagnostics,
        }
        manifest["force_clean_parent_rows_to_train"] = force_clean_parent_rows_to_train
        manifest["clean673_parent_test_overlap"] = len(test_ids & clean_parent_ids)
        if not force_clean_parent_rows_to_train:
            manifest["policy"] = split_policy
            manifest["forced_clean673_parent_train_rows"] = 0
            manifest["clean673_parent_train_test_overlap"] = len(
                test_ids & clean_parent_ids
            )
        tracked = [
            "train.pkl", "valid.pkl", "test.pkl", "mbjp_t5.json",
            "train_mbjp_t5.json", "valid_mbjp_t5.json", "test_mbjp_t5.json",
            "train_task_ids.json", "valid_task_ids.json", "test_task_ids.json",
            "mbjp_format.jsonl", "config.json", "loader_contract.json",
        ]
        manifest["artifact_sha256"] = {name: sha256(out / name) for name in tracked}
        dump_json(manifest, out / "parent_safe_split_manifest.json")
        dump_json(manifest, out / "split_manifest.json")
        os.replace(out, target)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", choices=["all", *SOURCES], default="all")
    parser.add_argument("--source-task")
    parser.add_argument("--target-task")
    parser.add_argument("--test-size", type=int)
    parser.add_argument("--allow-clean-parent-overlap", action="store_true")
    parser.add_argument("--data-revision")
    parser.add_argument("--split-policy")
    parser.add_argument("--reporting-label")
    parser.add_argument("--metadata-key")
    args = parser.parse_args()
    overrides = (args.source_task, args.target_task, args.test_size)
    if any(value is not None for value in overrides):
        if args.dataset == "all" or not all(value is not None for value in overrides):
            parser.error(
                "--source-task, --target-task, and --test-size must be supplied "
                "together for one explicit --dataset"
            )
        specs = {args.dataset: overrides}
    else:
        specs = SOURCES
    keys = list(specs) if args.dataset == "all" else [args.dataset]
    reports = [
        build(
            key,
            *specs[key],
            force_clean_parent_rows_to_train=not args.allow_clean_parent_overlap,
            data_revision=(
                args.data_revision or "java-expansion-parent-safe-v14-20260820"
            ),
            split_policy=(
                args.split_policy
                or "parent-safe MBJP-native fixed 80/20 interpolation; no validation"
            ),
            reporting_label=(
                args.reporting_label
                or "parent-safe MBJP-native exploratory interpolation evaluation"
            ),
            metadata_key=args.metadata_key or "parent_safe_v14",
        )
        for key in keys
    ]
    print(json.dumps(reports, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
