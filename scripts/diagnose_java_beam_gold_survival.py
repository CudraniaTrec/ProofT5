#!/usr/bin/env python
"""Trace the gold Java suffix through the exact no-CoqView beam frontier.

This is a diagnostic only: it does not generate benchmark candidates or write
to a model/output directory.  It reports the first decoder step at which the
gold continuation is no longer among the retained live beams.
"""

import argparse
import json
import os
import pickle
import sys
from copy import deepcopy
from pathlib import Path

import torch


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import Dataset
import beamsearch_coq
from Dataset import resolve_pad_token, rs_collate_fn_cutprefix
from ModelT5Gemma2 import MyT5Gemma2
from beamsearch_cache import reorder_cache
from run import Dotdict, load_model, load_rules_for_task, load_tokenizer_for_task


def strip_pad(values, pad_id):
    return [int(value) for value in values if int(value) != int(pad_id)]


def token_name(token_id):
    return beamsearch_coq.rrule_dict.get(int(token_id), f"<missing:{int(token_id)}>")


def global_frontier(log_probs, beams, cumulative_score, topk):
    """Return the exact pre-grammar global candidate order for live beams."""
    candidates = []
    for beam_index, node in enumerate(beams):
        valid_ids = beamsearch_coq.validtensors[node.expand_nodes[-1]]
        valid_index = torch.tensor(valid_ids, device=log_probs.device)
        count = min(topk, len(valid_ids))
        values, positions = torch.topk(
            log_probs[beam_index, valid_index], count, largest=True, sorted=True
        )
        for value, position in zip(values.tolist(), positions.tolist()):
            token = int(valid_ids[position])
            candidates.append(
                {
                    "origin": beam_index,
                    "token_id": token,
                    "token": token_name(token),
                    "score": float(value + cumulative_score[0, beam_index].item()),
                }
            )
    return sorted(candidates, key=lambda item: item["score"], reverse=True)


def load_checkpoint(task, model_output_task, model_type, device):
    config = Dotdict(json.load(open(f"Utils/data/{task}/config.json", "r")))
    config.update(
        {
            "task": task,
            "precision": "bf16",
            "mask_id": resolve_pad_token(config),
            "enable_coqview": False,
            "pretrain_name": config.get("pretrain_name", "pretrain_t5gemma2_2b"),
        }
    )
    runtime_rules = load_rules_for_task(task)
    try:
        pretrain_rules = load_rules_for_task(config.pretrain_name)
    except FileNotFoundError:
        # A direct parent can be a model-output tag rather than a data task.
        pretrain_rules = runtime_rules
    config.rulenum = len(pretrain_rules)
    model = MyT5Gemma2(config)
    load_model(model, f"Utils/models/Model{config.pretrain_name}/")
    config.rulenum = len(runtime_rules)
    model.resize_token_embeddings(config.rulenum, mean_resizing=False)
    load_model(model, f"Utils/models/Model{model_output_task}/", model_type=model_type)
    model.to(dtype=torch.bfloat16).eval().to(device)
    return model, config


@torch.no_grad()
def diagnose(args):
    model, config = load_checkpoint(
        args.task, args.model_output_task or args.task, args.model_type, args.device
    )
    rules = load_rules_for_task(args.task)
    tokenizer = load_tokenizer_for_task(args.task)
    beamsearch_coq.configure_runtime(rules, tokenizer_obj=tokenizer)
    Dataset.args = config
    Dataset.PAD_token = config.mask_id

    rows = pickle.load(open(f"Utils/data/{args.task}/{args.split}.pkl", "rb"))
    row = rows[args.sample_index]
    batch = rs_collate_fn_cutprefix([row])
    batch = {key: value.to(args.device) for key, value in batch.items()}
    target = strip_pad(batch["res"][0].tolist(), config.mask_id)

    initial = beamsearch_coq.SearchNode(int(config.get("max_coqview_len", 160)))
    prefix = strip_pad(batch["prefix"][0].tolist(), config.mask_id)
    if prefix and prefix[0] == rules["T_ClassDecl"]:
        for token in prefix[1:]:
            if not initial.apply(token, 0):
                raise RuntimeError(f"Initial prefix is grammar-invalid at {token_name(token)}")

    beam_size = args.beam_size
    input_nl = batch["nl"].repeat_interleave(beam_size, dim=0)
    encodenl, nlmask = model.encode_nl(input_nl)
    score = torch.full((1, beam_size), -1e10, device=args.device)
    score[0, 0] = 0.0
    beams = [initial]
    tmpstates = [initial.state] + [[0] * len(initial.state) for _ in range(beam_size - 1)]
    past_key_values = None
    gold_state = list(initial.state)
    records = []

    for step, gold_token in enumerate(target):
        state_tensor = torch.tensor(tmpstates, device=args.device)
        output, pastkv = beamsearch_coq.model_step_log_probs(
            model,
            encodenl,
            nlmask,
            state_tensor if past_key_values is None else state_tensor[:, -1:],
            past_key_values=past_key_values,
        )
        output = output[:, -1, :]

        cache_check = None
        if step == args.cache_check_step:
            gold_beam = next(
                (index for index, node in enumerate(beams) if node.state == gold_state),
                None,
            )
            if gold_beam is not None:
                # Replay the exact same gold prefix without a KV cache, while
                # retaining the beam batch shape.  Any material difference is
                # a cache/reordering defect rather than normal beam scoring.
                # Recompute each live beam's entire prefix. This lets us tell
                # whether ordinary BF16 cache drift changes the *global* beam
                # frontier, rather than merely changing an isolated logit.
                replay_states = [node.state for node in beams]
                while len(replay_states) < beam_size:
                    replay_states.append(replay_states[0])
                replay_input = torch.tensor(replay_states, device=args.device)
                replay_output, _ = beamsearch_coq.model_step_log_probs(
                    model, encodenl, nlmask, replay_input, past_key_values=None
                )
                replay_output = replay_output[:, -1, :]
                valid_ids = beamsearch_coq.validtensors[beams[gold_beam].expand_nodes[-1]]
                valid_index = torch.tensor(valid_ids, device=args.device)
                cached_row = output[gold_beam]
                replay_row = replay_output[gold_beam]
                frontier_topk = min(
                    beamsearch_coq.vocabsize,
                    max(2 * beam_size, args.candidate_multiplier * beam_size),
                )
                cached_frontier = global_frontier(
                    output, beams, score, frontier_topk
                )
                replay_frontier = global_frontier(
                    replay_output, beams, score, frontier_topk
                )
                compare_count = min(args.cache_frontier_topn, len(cached_frontier), len(replay_frontier))
                cache_check = {
                    "gold_beam": gold_beam,
                    "prefix_len": len(gold_state),
                    "max_abs_logprob_diff": float(
                        (cached_row - replay_row).abs().max().item()
                    ),
                    "gold_logprob_cached": float(cached_row[gold_token].item()),
                    "gold_logprob_replayed": float(replay_row[gold_token].item()),
                    "gold_rank_cached_among_valid": int(
                        (cached_row[valid_index] > cached_row[gold_token]).sum().item()
                    ) + 1,
                    "gold_rank_replayed_among_valid": int(
                        (replay_row[valid_index] > replay_row[gold_token]).sum().item()
                    ) + 1,
                    "all_live_beam_max_abs_logprob_diff": float(
                        (output[: len(beams)] - replay_output[: len(beams)]).abs().max().item()
                    ),
                    "global_frontier_same_origin_token_order": [
                        (cached_frontier[index]["origin"], cached_frontier[index]["token_id"])
                        == (replay_frontier[index]["origin"], replay_frontier[index]["token_id"])
                        for index in range(compare_count)
                    ],
                    "cached_global_frontier": cached_frontier[:compare_count],
                    "replayed_global_frontier": replay_frontier[:compare_count],
                }

        valid = torch.zeros(beam_size, beamsearch_coq.vocabsize, device=args.device)
        for beam_index, node in enumerate(beams):
            valid_ids = beamsearch_coq.validtensors[node.expand_nodes[-1]]
            valid[beam_index, valid_ids] = 1
        output = output.masked_fill(valid == 0, -900)
        topk = min(
            beamsearch_coq.vocabsize,
            max(2 * beam_size, args.candidate_multiplier * beam_size),
        )
        per_beam_scores, per_beam_tokens = torch.topk(
            output, topk, dim=-1, largest=True, sorted=True
        )
        per_beam_scores = per_beam_scores + score.view(-1).unsqueeze(1)
        origins = (
            torch.arange(beam_size, device=args.device)
            .unsqueeze(1)
            .repeat(1, topk)
        )
        flat_scores = per_beam_scores.reshape(1, -1)
        flat_tokens = per_beam_tokens.reshape(1, -1)
        flat_origins = origins.reshape(1, -1)
        ordered_scores, ordered_positions = torch.sort(flat_scores, descending=True)
        ordered_tokens = flat_tokens.gather(1, ordered_positions)
        ordered_origins = flat_origins.gather(1, ordered_positions)

        gold_state.append(gold_token)
        gold_candidate_rank = None
        gold_candidate_score = None
        gold_candidate_origin = None
        next_beams = []
        next_states = []
        next_origins = []
        next_scores = []
        gold_kept_rank = None
        gold_finished = False
        attempted = 0
        for candidate_index in range(ordered_tokens.size(1)):
            # Match BeamSearch exactly: once it has filled the next live beam
            # set it does not inspect any lower-scoring candidate.
            if len(next_beams) >= beam_size:
                break
            candidate_score = float(ordered_scores[0, candidate_index].item())
            if candidate_score < -800:
                break
            origin = int(ordered_origins[0, candidate_index].item())
            if origin >= len(beams):
                continue
            token = int(ordered_tokens[0, candidate_index].item())
            node = deepcopy(beams[origin])
            if not node.apply(token, candidate_score):
                continue
            attempted += 1
            is_gold = node.state == gold_state
            if is_gold and gold_candidate_rank is None:
                gold_candidate_rank = candidate_index + 1
                gold_candidate_score = candidate_score
                gold_candidate_origin = origin
            if node.isfinish:
                if is_gold:
                    gold_finished = True
                continue
            next_beams.append(node)
            next_states.append(node.state)
            next_origins.append(origin)
            next_scores.append(node.prob)
            if is_gold:
                gold_kept_rank = len(next_beams)

        records.append(
            {
                "step": step,
                "gold_id": gold_token,
                "gold_token": token_name(gold_token),
                "gold_candidate_rank_in_global_frontier": gold_candidate_rank,
                "gold_candidate_score": gold_candidate_score,
                "gold_candidate_origin": gold_candidate_origin,
                "gold_kept_live_rank": gold_kept_rank,
                "gold_finished": gold_finished,
                "live_beams_after": len(next_beams),
                "valid_candidates_attempted": attempted,
                "frontier_top": [
                    {
                        "rank": rank + 1,
                        "origin": int(ordered_origins[0, rank].item()),
                        "token": token_name(int(ordered_tokens[0, rank].item())),
                        "score": float(ordered_scores[0, rank].item()),
                    }
                    for rank in range(min(args.topn, ordered_tokens.size(1)))
                ],
                "cache_check": cache_check,
            }
        )
        if gold_kept_rank is None and not gold_finished:
            break
        if gold_finished:
            break

        state_len = len(next_states[0]) if next_states else len(gold_state)
        while len(next_states) < beam_size:
            next_states.append([0] * state_len)
            next_origins.append(0)
            next_scores.append(-1e9)
        score.fill_(-1e9)
        score[0, : len(next_beams)] = torch.tensor(
            next_scores[: len(next_beams)], device=args.device
        )
        past_key_values = reorder_cache(
            pastkv, torch.tensor(next_origins, device=args.device, dtype=torch.long)
        )
        beams = next_beams
        tmpstates = next_states

    first_loss = next(
        (
            record
            for record in records
            if record["gold_kept_live_rank"] is None and not record["gold_finished"]
        ),
        None,
    )
    return {
        "task": args.task,
        "split": args.split,
        "sample_index": args.sample_index,
        "model_output_task": args.model_output_task or args.task,
        "model_type": args.model_type,
        "beam_size": beam_size,
        "candidate_multiplier": args.candidate_multiplier,
        "prefix_length": len(initial.state),
        "target_length": len(target),
        "first_gold_loss": first_loss,
        "gold_completed": bool(records and records[-1]["gold_finished"]),
        "records": records,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--split", choices=["train", "valid", "test"], default="test")
    parser.add_argument("--sample_index", type=int, required=True)
    parser.add_argument("--model_output_task", default="")
    parser.add_argument("--model_type", default="last")
    parser.add_argument("--beam_size", type=int, default=10)
    parser.add_argument("--candidate_multiplier", type=int, default=20)
    parser.add_argument("--topn", type=int, default=12)
    parser.add_argument("--cache_check_step", type=int, default=-1)
    parser.add_argument("--cache_frontier_topn", type=int, default=20)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--json_out", default="")
    args = parser.parse_args()
    result = diagnose(args)
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    if args.json_out:
        Path(args.json_out).write_text(rendered + "\n")


if __name__ == "__main__":
    main()
