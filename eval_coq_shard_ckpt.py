"""Checkpoint-addressable variant of eval_coq_shard.py.

Identical to eval_coq_shard.py (same beamsearch_coq.BeamSearch decoder, same
decode arguments, same output format) except that the evaluated checkpoint is
given explicitly via --model_dir/--model_type instead of being derived from
the task name. The pretrain reload is skipped because the loaded checkpoint is
a complete final model whose embedding rows already match len(rules).
"""

import argparse
import json
import os
import pickle
import time

import torch

from Dataset import pad_seq, resolve_pad_token
from ModelT5Gemma2 import MyT5Gemma2
from beamsearch_coq import BeamSearch
from run import Dotdict, load_model, load_rules_for_task, load_tokenizer_for_task
from eval_coq_shard import output_candidate_complete


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--split", choices=["train", "valid", "test"], required=True)
    parser.add_argument("--start", type=int, required=True)
    parser.add_argument("--end", type=int, required=True)
    parser.add_argument("--model_dir", required=True)
    parser.add_argument("--model_type", default="last")
    parser.add_argument("--output_tag", required=True)
    parser.add_argument("--beamsize", type=int, default=10)
    parser.add_argument("--coq_candidate_multiplier", type=int, default=2)
    parser.add_argument("--coq_workers", type=int, default=20)
    parser.add_argument("--coq_timeout", type=int, default=20)
    parser.add_argument("--disable_coq_check", action="store_true")
    parser.add_argument("--early_stop_after_final_steps", type=int, default=-1)
    parser.add_argument("--early_stop_max_first_final_len", type=int, default=-1)
    parser.add_argument("--length_penalty", type=float, default=0.1)
    parser.add_argument("--resume_output", action="store_true")
    args = parser.parse_args()

    config = Dotdict(json.load(open(f"Utils/data/{args.task}/config.json", "r")))
    config.update(
        {
            "task": args.task,
            "precision": "bf16",
            "mask_id": resolve_pad_token(config),
            "enable_coqview": False,
        }
    )
    rules = load_rules_for_task(args.task)
    config.rulenum = len(rules)
    model = MyT5Gemma2(config)
    load_model(model, args.model_dir, model_type=args.model_type)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.eval().to(device)

    data = pickle.load(open(f"Utils/data/{args.task}/{args.split}.pkl", "rb"))
    target_folder = f"Utils/output/{args.task}_{args.split}_ans/{args.output_tag}/"
    os.makedirs(target_folder, exist_ok=True)

    early_stop_after_final_steps = (
        None if args.early_stop_after_final_steps < 0 else args.early_stop_after_final_steps
    )
    early_stop_max_first_final_len = (
        None if args.early_stop_max_first_final_len < 0 else args.early_stop_max_first_final_len
    )
    beam = BeamSearch(
        args.beamsize,
        rules,
        length_penalty=args.length_penalty,
        tokenizer_obj=load_tokenizer_for_task(args.task),
        checkcoq=not args.disable_coq_check,
        check_grammar=True,
        candidate_multiplier=args.coq_candidate_multiplier,
        coq_workers=args.coq_workers,
        coq_timeout=args.coq_timeout,
        early_stop_after_final_steps=early_stop_after_final_steps,
        early_stop_max_first_final_len=early_stop_max_first_final_len,
        disable_tqdm=True,
    )

    for idx in range(args.start, min(args.end, len(data))):
        paths = [f"{target_folder}{idx}_{k}.txt" for k in range(args.beamsize)]
        if args.resume_output and output_candidate_complete(paths[0]):
            print(f"{idx} already has top0 in {target_folder}", flush=True)
            continue

        row = data[idx]
        nl_len = min(len(row["nl"]), config.NlLen)
        input_nl = torch.tensor([pad_seq(row["nl"], nl_len)], device=device)
        started = time.time()
        with torch.no_grad():
            ans = beam.search(
                input_nl.repeat_interleave(args.beamsize, dim=0),
                model,
                max_len=config.CodeLen,
                offset=idx,
            )
        final_set = ans[0].final_set
        for k in range(args.beamsize):
            if k >= len(final_set):
                if os.path.exists(paths[k]):
                    os.remove(paths[k])
                continue
            with open(paths[k], "w") as f:
                f.write(final_set[k])
        print(
            f"{idx} saved {len(final_set)} candidates to {target_folder} in {time.time() - started:.1f}s",
            flush=True,
        )


if __name__ == "__main__":
    main()
