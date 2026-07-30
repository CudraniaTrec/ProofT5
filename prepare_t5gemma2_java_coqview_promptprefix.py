import argparse
import copy
import json
import multiprocessing as mp
import os
import pickle
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from tqdm import tqdm


sys.path.insert(0, os.path.abspath("coq_model"))

import program_model  # noqa: E402
from program_model import detokenization_wrapper, extract_context  # noqa: E402


DEFAULT_SRC_TASK = "mbjpcoq_t5gemma2_2b_retok_promptprefix_lr1e4"
DEFAULT_DST_TASK = "mbjpcoqview_t5gemma2_2b_retok_promptprefix_lr5e5_from_java_anchor32_replay8x2"
DEFAULT_PRETRAIN_NAME = "mbjpcoq_t5gemma2_2b_retok_promptprefix_lr1e4"

_TOKENIZER = None
_WORK_TMP_ROOT = None
_COQC_TIMEOUT = 60


def load_pickle(path):
    with open(path, "rb") as f:
        return pickle.load(f)


def dump_pickle(obj, path):
    with open(path, "wb") as f:
        pickle.dump(obj, f)


def dump_json(obj, path):
    with open(path, "w") as f:
        json.dump(obj, f, indent=2)


def init_worker(tokenizer, tmp_root, coqc_timeout):
    global _TOKENIZER, _WORK_TMP_ROOT, _COQC_TIMEOUT
    _TOKENIZER = tokenizer
    _WORK_TMP_ROOT = tmp_root
    _COQC_TIMEOUT = coqc_timeout
    program_model.tokenizer = tokenizer


def cleanup_stem(path):
    stem = Path(path).with_suffix("")
    for suffix in [".v", ".vo", ".vos", ".vok", ".glob", ".aux"]:
        for candidate in [
            stem.with_suffix(suffix),
            stem.with_name(f".{stem.name}").with_suffix(suffix),
        ]:
            if candidate.exists():
                candidate.unlink()


def coqview_for_prefix(tokens, split, row_idx, step_idx):
    proof = detokenization_wrapper(tokens[: step_idx + 1])
    if proof is None:
        raise RuntimeError(f"{split}[{row_idx}] step {step_idx + 1}: detokenization failed")

    worker_dir = Path(_WORK_TMP_ROOT) / f"worker_{os.getpid()}"
    worker_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".v",
        prefix=f"{split}_{row_idx}_{step_idx + 1}_",
        dir=worker_dir,
        delete=False,
    ) as f:
        coq_path = f.name
        f.write(str(proof.to_coq()))

    try:
        res = subprocess.run(
            ["coqc", "-Q", "coq_model/coq_code", "PLF", coq_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=_COQC_TIMEOUT,
        )
        if res.returncode != 0:
            stderr = res.stderr.decode("utf-8", errors="replace")[:500]
            raise RuntimeError(
                f"{split}[{row_idx}] step {step_idx + 1}: coqc failed with {res.returncode}: {stderr}"
            )
        context = extract_context(res.stdout.decode("utf-8", errors="replace"))
        return context, _TOKENIZER.encode(context)[1:-1]
    finally:
        cleanup_stem(coq_path)


def convert_row(args):
    split, row_idx, row = args
    tokens = row["tokens"]
    coqview = []
    raw_contexts = []
    for step_idx in range(len(tokens) - 1):
        raw, encoded = coqview_for_prefix(tokens, split, row_idx, step_idx)
        raw_contexts.append(raw)
        coqview.append(encoded)

    new_row = copy.deepcopy(row)
    new_row["coqview"] = coqview
    new_row["coqview_raw"] = "".join(raw_contexts)
    expected = len(new_row["rulelist"][1:-1]) - 1
    if len(coqview) != expected:
        raise RuntimeError(
            f"{split}[{row_idx}] coqview length {len(coqview)} != expected {expected}"
        )
    return row_idx, new_row


def parse_row_indices(value):
    if not value:
        return None
    indices = []
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        indices.append(int(item))
    return indices


def convert_split(src_dir, dst_dir, split, workers, limit, row_indices, tokenizer, tmp_root, coqc_timeout):
    rows = load_pickle(src_dir / f"{split}.pkl")
    if row_indices is None:
        selected_indices = list(range(len(rows)))
        if limit is not None:
            selected_indices = selected_indices[:limit]
    else:
        selected_indices = [idx for idx in row_indices if idx < len(rows)]

    cache_dir = dst_dir / "_row_cache" / split
    cache_dir.mkdir(parents=True, exist_ok=True)
    converted_by_idx = {}
    max_coqview_len = 0
    jobs = []

    for idx in selected_indices:
        cache_path = cache_dir / f"{idx}.pkl"
        if cache_path.exists():
            row = load_pickle(cache_path)
            converted_by_idx[idx] = row
            for context in row["coqview"]:
                max_coqview_len = max(max_coqview_len, len(context))
        else:
            jobs.append((split, idx, rows[idx]))

    if jobs:
        with mp.Pool(
            processes=workers,
            initializer=init_worker,
            initargs=(tokenizer, tmp_root, coqc_timeout),
        ) as pool:
            for idx, row in tqdm(
                pool.imap_unordered(convert_row, jobs),
                total=len(jobs),
                desc=f"{split} coqview",
            ):
                converted_by_idx[idx] = row
                dump_pickle(row, cache_dir / f"{idx}.pkl")
                for context in row["coqview"]:
                    max_coqview_len = max(max_coqview_len, len(context))

    converted = [converted_by_idx[idx] for idx in selected_indices]
    return converted, max_coqview_len


def copy_task_files(src_dir, dst_dir):
    for name in ["rules.pkl", "rules.json", "tokenizer.pkl", "coq_tokenizer.pkl", "groundvalid.txt"]:
        src = src_dir / name
        if src.exists():
            shutil.copy2(src, dst_dir / name)


def validate_cut_prefix(rows):
    bad = []
    for idx, row in enumerate(rows):
        target = row["rulelist"][1:-1]
        prefix = row["prefix"]
        if target[: len(prefix)] != prefix:
            bad.append((idx, "prefix_mismatch", len(prefix), len(target)))
            continue
        expected = len(target) - len(prefix)
        got = len(row["coqview"]) - max(len(prefix) - 1, 0)
        if expected != got:
            bad.append((idx, "coqview_len", expected, got))
    if bad:
        raise RuntimeError(f"cut-prefix validation failed: {bad[:10]}")


def write_config(src_dir, dst_dir, dst_task, pretrain_name, max_coqview_len, smoke):
    config = json.load(open(src_dir / "config.json"))
    config.update(
        {
            "batch_size": 2,
            "batch_size_eval": 1,
            "lr": 0.00005,
            "max_epoch": 80,
            "patience": 5,
            "max_num_trials": 3,
            "eval_step": 5,
            "eval_step_init": 5,
            "max_coqview_len": max_coqview_len,
            "validation": False,
            "cut_prefix": True,
            "empty_cuda_cache": 20,
            "enable_coqview": True,
            "coqview_train_steps": 16,
            "coqview_anchor_first_steps": 32,
            "coqview_random_window_steps": 2,
            "coqview_max_step_offset": 0,
            "coqview_prefix_replay_steps": 8,
            "coqview_prefix_replay_repeats": 2,
            "pretrain_name": pretrain_name,
        }
    )
    if smoke:
        config["max_epoch"] = 1
        config["eval_step"] = 1
        config["eval_step_init"] = 1
    dump_json(config, dst_dir / "config.json")

    model_dir = Path("Utils") / "models" / f"Model{dst_task}"
    model_dir.mkdir(parents=True, exist_ok=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--src-task", default=DEFAULT_SRC_TASK)
    parser.add_argument("--dst-task", default=DEFAULT_DST_TASK)
    parser.add_argument("--pretrain-name", default=DEFAULT_PRETRAIN_NAME)
    parser.add_argument("--workers", type=int, default=max(1, min(32, os.cpu_count() or 1)))
    parser.add_argument("--limit", type=int)
    parser.add_argument("--row-indices", help="Comma-separated original row indices to convert for every selected split")
    parser.add_argument("--splits", nargs="+", default=["train", "valid", "test"])
    parser.add_argument("--coqc-timeout", type=int, default=60)
    parser.add_argument("--tmp-root", default="tmp/java_retok_coqview_build")
    args = parser.parse_args()

    src_dir = Path("Utils") / "data" / args.src_task
    dst_dir = Path("Utils") / "data" / args.dst_task
    if not src_dir.exists():
        raise FileNotFoundError(src_dir)
    dst_dir.mkdir(parents=True, exist_ok=True)
    Path(args.tmp_root).mkdir(parents=True, exist_ok=True)

    tokenizer = load_pickle(src_dir / "tokenizer.pkl")
    program_model.tokenizer = tokenizer

    mp.set_start_method("fork", force=True)
    split_rows = {}
    max_coqview_len = 0
    row_indices = parse_row_indices(args.row_indices)
    for split in args.splits:
        rows, split_max = convert_split(
            src_dir,
            dst_dir,
            split,
            args.workers,
            args.limit,
            row_indices,
            tokenizer,
            args.tmp_root,
            args.coqc_timeout,
        )
        validate_cut_prefix(rows)
        split_rows[split] = rows
        max_coqview_len = max(max_coqview_len, split_max)

    for split, rows in split_rows.items():
        dump_pickle(rows, dst_dir / f"{split}.pkl")
        dump_json(rows, dst_dir / f"{split}.json")

    copy_task_files(src_dir, dst_dir)
    write_config(
        src_dir,
        dst_dir,
        args.dst_task,
        args.pretrain_name,
        max_coqview_len,
        args.limit is not None,
    )

    print(f"wrote {dst_dir}")
    print(f"max_coqview_len={max_coqview_len}")
    for split, rows in split_rows.items():
        print(f"{split}: {len(rows)} rows")


if __name__ == "__main__":
    main()
