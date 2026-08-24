#!/usr/bin/env python3
"""Build a paper-route CoqView task from an audited complete training task.

The builder never trusts a similarly named historical task.  It reuses a
historical CoqView sequence only when the token/rule artifacts match and a
language-specific proof signature is identical.  Remaining rows are converted
with the current Java or SuFu converter.  ``--dry-run`` is read-only and shows
the exact conversion work before creating a target task.
"""

import argparse
import copy
import hashlib
import json
import multiprocessing as mp
import os
import pickle
import shutil
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


ARTIFACTS = ("rules.pkl", "rules.json", "tokenizer.pkl", "coq_tokenizer.pkl")
SPLITS = ("train", "valid", "test")
SIGNATURE_FIELDS = {
    # java_code is intentionally absent: it is formatted differently in the
    # historical CoqView task, while the rule tokens, proof tokens, and prompt
    # are identical and uniquely determine the CoqView trace.  The Java
    # converter reads only ``tokens``; the executable test harness therefore
    # must not invalidate a reusable proof-state trace (v5 changes only that
    # harness while preserving the prompt, solution, IR, and proof tokens).
    "java": ("rulelist", "prefix", "tokens", "nl"),
    "sufu": ("rulelist", "prefix", "nl", "code", "file_name", "output", "postfix"),
}


def load_pickle(path):
    with path.open("rb") as handle:
        return pickle.load(handle)


def dump_pickle(value, path):
    with path.open("wb") as handle:
        pickle.dump(value, handle)


def dump_json(value, path):
    with path.open("w") as handle:
        json.dump(value, handle, indent=2)
        handle.write("\n")


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def row_signature(row, signature_fields):
    if isinstance(signature_fields, str):
        signature_fields = SIGNATURE_FIELDS[signature_fields]
    values = tuple(row.get(field) for field in signature_fields)
    return hashlib.sha256(pickle.dumps(values, protocol=4)).hexdigest()


def expected_context_steps(row):
    return len(row["rulelist"][1:-1]) - 1


def check_artifacts(source_dir, reference_dir, template_dir):
    report = {}
    for name in ARTIFACTS:
        source = source_dir / name
        if not source.exists():
            raise FileNotFoundError(f"Missing source artifact: {source}")
        source_hash = sha256(source)
        values = {"source": source_hash}
        for label, directory in (("reference", reference_dir), ("template", template_dir)):
            candidate = directory / name
            if not candidate.exists():
                raise FileNotFoundError(f"Missing {label} artifact: {candidate}")
            candidate_hash = sha256(candidate)
            values[label] = candidate_hash
            if candidate_hash != source_hash:
                raise RuntimeError(
                    f"Artifact mismatch for {name}: source={source_hash}, "
                    f"{label}={candidate_hash}"
                )
        report[name] = values
    return report


def load_split(directory, split):
    path = directory / f"{split}.pkl"
    return load_pickle(path) if path.exists() else []


def validate_context(row, language, vocabulary_size, where):
    contexts = row.get("coqview")
    expected = expected_context_steps(row)
    if not isinstance(contexts, list) or len(contexts) != expected:
        got = len(contexts) if isinstance(contexts, list) else type(contexts).__name__
        raise RuntimeError(f"{where}: expected {expected} CoqView steps, got {got}")
    for step, context in enumerate(contexts):
        if not isinstance(context, list):
            raise RuntimeError(f"{where}: context {step} is not a list")
        if any(not isinstance(token, int) or token < 0 or token >= vocabulary_size for token in context):
            raise RuntimeError(f"{where}: context {step} has an out-of-vocabulary token")
    if language == "java" and "coqview_raw" not in row:
        raise RuntimeError(f"{where}: Java CoqView row lacks coqview_raw")


def donor_index(reference_dirs, language, vocabulary_size, signature_fields=None):
    if isinstance(reference_dirs, Path):
        reference_dirs = [reference_dirs]
    signature_fields = signature_fields or SIGNATURE_FIELDS[language]
    index = {}
    for reference_dir in reference_dirs:
        for split in SPLITS:
            for row_index, row in enumerate(load_split(reference_dir, split)):
                if "coqview" not in row:
                    continue
                where = f"reference {reference_dir.name} {split}[{row_index}]"
                validate_context(row, language, vocabulary_size, where)
                signature = row_signature(row, signature_fields)
                existing = index.get(signature)
                if existing is not None:
                    previous = pickle.dumps(existing["coqview"], protocol=4)
                    current = pickle.dumps(row["coqview"], protocol=4)
                    if previous != current:
                        raise RuntimeError(
                            f"Ambiguous reference CoqView sequence for signature {signature[:16]}"
                        )
                    continue
                index[signature] = row
    return index


def build_plan(source_dir, reference_dirs, language, vocabulary_size, signature_fields=None):
    signature_fields = signature_fields or SIGNATURE_FIELDS[language]
    donors = donor_index(reference_dirs, language, vocabulary_size, signature_fields)
    plan = {}
    missing = {}
    for split in SPLITS:
        rows = load_split(source_dir, split)
        reuse = []
        convert = []
        for row_index, row in enumerate(rows):
            donor = donors.get(row_signature(row, signature_fields))
            if donor is None:
                convert.append(row_index)
            else:
                if expected_context_steps(row) != expected_context_steps(donor):
                    raise RuntimeError(f"{split}[{row_index}]: donor target length differs")
                reuse.append(row_index)
        plan[split] = {"rows": len(rows), "reuse": len(reuse), "convert": len(convert)}
        missing[split] = convert
    return donors, plan, missing


def convert_java_rows(rows, row_indices, split, tokenizer, cache_dir, workers, coqc_timeout):
    """Convert Java rows, caching each result outside the output task."""
    if not row_indices:
        return {}
    import prepare_t5gemma2_java_coqview_promptprefix as java_converter

    cache_dir.mkdir(parents=True, exist_ok=True)
    converted = {}
    jobs = []
    for row_index in row_indices:
        cache_path = cache_dir / f"{split}_{row_index}.pkl"
        if cache_path.exists():
            converted[row_index] = load_pickle(cache_path)
        else:
            jobs.append((split, row_index, rows[row_index]))
    if jobs:
        # Coq compilation is independent per row.  Forking is deliberate: the
        # converter and its tokenizer were written for Linux fork workers.
        context = mp.get_context("fork")
        with context.Pool(
            processes=workers,
            initializer=java_converter.init_worker,
            initargs=(tokenizer, cache_dir, coqc_timeout),
        ) as pool:
            for row_index, row in pool.imap_unordered(java_converter.convert_row, jobs):
                dump_pickle(row, cache_dir / f"{split}_{row_index}.pkl")
                converted[row_index] = row
    return converted


def convert_sufu_rows(rows, row_indices, split, tokenizer, rules):
    if not row_indices:
        return {}
    import prepare_t5gemma2_sufu_coqview_ctxfix as sufu_converter

    converted = {}
    for row_index in row_indices:
        row = copy.deepcopy(rows[row_index])
        row["coqview"] = sufu_converter.build_contexts(
            row, tokenizer, rules, split, row_index
        )
        converted[row_index] = row
    return converted


def attach_context(source_row, donor, language):
    row = copy.deepcopy(source_row)
    row["coqview"] = copy.deepcopy(donor["coqview"])
    if language == "java":
        row["coqview_raw"] = donor["coqview_raw"]
    return row


def build_rows(
    source_dir, donors, missing, language, tokenizer, rules, cache_dir, workers,
    coqc_timeout, signature_fields=None,
):
    signature_fields = signature_fields or SIGNATURE_FIELDS[language]
    output = {}
    for split in SPLITS:
        source_rows = load_split(source_dir, split)
        if language == "java":
            converted = convert_java_rows(
                source_rows, missing[split], split, tokenizer, cache_dir, workers, coqc_timeout
            )
        else:
            converted = convert_sufu_rows(source_rows, missing[split], split, tokenizer, rules)
        rows = []
        for row_index, row in enumerate(source_rows):
            donor = donors.get(row_signature(row, signature_fields))
            rows.append(attach_context(row, donor, language) if donor is not None else converted[row_index])
        output[split] = rows
    return output


def write_task(
    target_dir,
    source_dir,
    reference_dirs,
    template_dir,
    target_task,
    parent_task,
    parent_checkpoint,
    rows_by_split,
    plan,
    artifact_report,
    language,
    signature_fields=None,
):
    signature_fields = signature_fields or SIGNATURE_FIELDS[language]
    if isinstance(reference_dirs, Path):
        reference_dirs = [reference_dirs]
    target_dir.mkdir(parents=True)
    try:
        tokenizer = load_pickle(source_dir / "tokenizer.pkl")
        vocabulary_size = len(tokenizer)
        max_context = 0
        for split, rows in rows_by_split.items():
            for row_index, row in enumerate(rows):
                validate_context(row, language, vocabulary_size, f"output {split}[{row_index}]")
                max_context = max(max_context, *(map(len, row["coqview"]) or [0]))
            dump_pickle(rows, target_dir / f"{split}.pkl")
            dump_json(rows, target_dir / f"{split}.json")

        for name in ARTIFACTS:
            shutil.copy2(source_dir / name, target_dir / name)
        source_config = json.loads((source_dir / "config.json").read_text())
        config = json.loads((template_dir / "config.json").read_text())
        # Dataset bounds belong to the new audited source, not to the older
        # CoqView template. Reusing a smaller historical CodeLen silently
        # truncates full-sequence training examples before they reach the
        # CoqView loss loop.
        for key in ("CodeLen", "max_code_len", "NlLen"):
            if key in source_config:
                config[key] = source_config[key]
        config.update(
            {
                "pretrain_name": parent_task,
                "pretrain_model_type": "last",
                "enable_coqview": True,
                "validation": False,
                # Preserve explicit test-only isolation for evaluation tasks;
                # complete training sources keep this false.
                "evaluation_only": bool(source_config.get("evaluation_only", False)),
                "contains_debug_split": False,
                "cut_prefix": True,
                "batch_size": 1,
                "batch_size_eval": 1,
                "lr": 1e-6,
                "max_coqview_len": max_context,
                "coqview_train_steps": 0,
                "coqview_anchor_first_steps": 0,
                "coqview_random_window_steps": None,
                "coqview_prefix_replay_steps": 0,
                "coqview_prefix_replay_repeats": 0,
                "coqview_suffix_replay_steps": 0,
                "coqview_suffix_replay_repeats": 0,
                "coqview_loss_reduction": "mean",
                "coqview_sync_last_only": True,
                "coqview_manual_distributed": True,
                "coqview_history_gradient_policy": "streaming_detached_self_kv",
                "beam_score_policy": "fp32_log_softmax_logits",
                "strict_model_loading": True,
                "data_revision": "complete-training-frozen-paper-test-coqview-v1",
                "complete_training_rows": len(rows_by_split["train"]),
                "benchmark_test_rows": len(rows_by_split["test"]),
                "source_data_revision": source_config.get("data_revision"),
            }
        )
        (target_dir / "config.json").write_text(json.dumps(config, indent=2) + "\n")
        manifest = {
            "target_task": target_task,
            "language": language,
            "source_task": source_dir.name,
            "reference_coqview_task": reference_dirs[0].name,
            "reference_coqview_tasks": [directory.name for directory in reference_dirs],
            "config_template_task": template_dir.name,
            "direct_parent_task": parent_task,
            "direct_parent_checkpoint": str(parent_checkpoint),
            "direct_parent_sha256": sha256(parent_checkpoint),
            "signature_fields": list(signature_fields),
            "nl_only_donor_reuse": language == "java" and "nl" not in signature_fields,
            "artifact_sha256": artifact_report,
            "split_plan": plan,
            "max_coqview_len": max_context,
            "validation_rows": len(rows_by_split["valid"]),
            "data_revision": config["data_revision"],
        }
        (target_dir / "coqview_build_manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n"
        )
    except Exception:
        shutil.rmtree(target_dir)
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--language", choices=("java", "sufu"), required=True)
    parser.add_argument("--source-task", required=True)
    parser.add_argument("--reference-coqview-task", required=True)
    parser.add_argument(
        "--extra-reference-coqview-task",
        action="append",
        default=[],
        help="additional audited donor task; may be supplied more than once",
    )
    parser.add_argument("--config-template-task", required=True)
    parser.add_argument("--target-task", required=True)
    parser.add_argument("--parent-task", required=True)
    parser.add_argument("--data-root", default="Utils/data")
    parser.add_argument("--model-root", default="Utils/models")
    parser.add_argument("--cache-dir", default="")
    parser.add_argument("--workers", type=int, default=max(1, min(16, os.cpu_count() or 1)))
    parser.add_argument("--coqc-timeout", type=int, default=60)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--allow-java-nl-only-donor",
        action="store_true",
        help=(
            "reuse Java CoqView traces when rulelist/prefix/tokens match even if only the "
            "encoder nl changed; the source row and its new nl are retained"
        ),
    )
    args = parser.parse_args()
    if args.allow_java_nl_only_donor and args.language != "java":
        parser.error("--allow-java-nl-only-donor is Java-only")

    data_root = Path(args.data_root)
    source_dir = data_root / args.source_task
    reference_dirs = [data_root / args.reference_coqview_task]
    reference_dirs.extend(data_root / name for name in args.extra_reference_coqview_task)
    template_dir = data_root / args.config_template_task
    target_dir = data_root / args.target_task
    parent_checkpoint = Path(args.model_root) / f"Model{args.parent_task}" / "last_model.ckpt"
    if not source_dir.exists() or any(not directory.exists() for directory in reference_dirs) or not template_dir.exists():
        raise FileNotFoundError("source, reference, and template tasks must exist")
    if target_dir.exists() and not args.dry_run:
        raise FileExistsError(f"Refusing to overwrite target task: {target_dir}")
    if not parent_checkpoint.exists():
        raise FileNotFoundError(
            f"Expected selected ordinary parent checkpoint: {parent_checkpoint}"
        )

    artifacts = check_artifacts(source_dir, reference_dirs[0], template_dir)
    for extra_reference in reference_dirs[1:]:
        for name in ARTIFACTS:
            extra_hash = sha256(extra_reference / name)
            if extra_hash != artifacts[name]["source"]:
                raise RuntimeError(
                    f"Artifact mismatch for {name}: source={artifacts[name]['source']}, "
                    f"extra reference {extra_reference.name}={extra_hash}"
                )
            artifacts[name][f"extra_reference:{extra_reference.name}"] = extra_hash
    vocabulary_size = len(load_pickle(source_dir / "tokenizer.pkl"))
    signature_fields = SIGNATURE_FIELDS[args.language]
    if args.allow_java_nl_only_donor:
        signature_fields = tuple(field for field in signature_fields if field != "nl")
    donors, plan, missing = build_plan(
        source_dir, reference_dirs, args.language, vocabulary_size, signature_fields
    )
    report = {
        "language": args.language,
        "source_task": args.source_task,
        "reference_coqview_task": args.reference_coqview_task,
        "extra_reference_coqview_tasks": args.extra_reference_coqview_task,
        "config_template_task": args.config_template_task,
        "target_task": args.target_task,
        "parent_task": args.parent_task,
        "signature_fields": list(signature_fields),
        "nl_only_donor_reuse": args.allow_java_nl_only_donor,
        "artifact_sha256": artifacts,
        "split_plan": plan,
        "dry_run": args.dry_run,
    }
    if args.dry_run:
        print(json.dumps(report, indent=2))
        return

    tokenizer = load_pickle(source_dir / "tokenizer.pkl")
    rules = load_pickle(source_dir / "rules.pkl")
    cache_dir = Path(args.cache_dir) if args.cache_dir else Path("tmp") / f"{args.target_task}_coqview_cache"
    rows = build_rows(
        source_dir, donors, missing, args.language, tokenizer, rules, cache_dir,
        args.workers, args.coqc_timeout, signature_fields=signature_fields,
    )
    write_task(
        target_dir, source_dir, reference_dirs, template_dir, args.target_task,
        args.parent_task, parent_checkpoint, rows, plan, artifacts, args.language,
        signature_fields=signature_fields,
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
