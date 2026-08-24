import argparse
import io
import json
import os
import pickle
import sys
from pathlib import Path

import torch

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import Dataset
import beamsearch_coq
import beamsearch_sufu
from Dataset import rs_collate_fn_cutprefix
from run import Dotdict, load_rules_for_task, load_tokenizer_for_task


JAVA_TASK = "mbjpcoqview_t5gemma2_2b_corrected_from_java30_fullseq_prefixpadfix_b1_20260718"
SUFU_TASK = "sufucoqview_t5gemma2_2b_corrected_from_sufu60_fullseq_b1_20260718"


class TraceCache:
    def __init__(self):
        self.reorders = []

    def reorder_cache(self, beam_idx):
        self.reorders.append(beam_idx.detach().cpu().tolist())


class ForcedGoldModel:
    def __init__(self, gold_tokens, vocab_size, return_logits):
        self.gold_tokens = list(gold_tokens)
        self.vocab_size = vocab_size
        self.return_logits = return_logits
        self.calls = []
        self.cache = TraceCache()

    def encode_nl(self, inputnl):
        return inputnl, torch.ne(inputnl, 0)

    def _step(self, inputrule, inputcoqview, past_key_values):
        step = len(self.calls)
        assert step < len(self.gold_tokens), (step, len(self.gold_tokens))
        self.calls.append(
            {
                "inputrule": inputrule.detach().cpu().clone(),
                "inputcoqview": (
                    inputcoqview.detach().cpu().clone()
                    if inputcoqview is not None
                    else None
                ),
                "had_cache": past_key_values is not None,
            }
        )
        scores = torch.full(
            (inputrule.size(0), 1, self.vocab_size),
            -1000.0 if self.return_logits else 0.0,
            device=inputrule.device,
        )
        scores[:, 0, self.gold_tokens[step]] = 0.0 if self.return_logits else 1.0
        return scores, self.cache

    def test_forward(
        self,
        encodenl,
        nlmask,
        inputrule,
        inputcoqview=None,
        past_key_values=None,
    ):
        assert not self.return_logits
        return self._step(inputrule, inputcoqview, past_key_values)

    def test_forward_logits(
        self,
        encodenl,
        nlmask,
        inputrule,
        inputcoqview=None,
        past_key_values=None,
    ):
        assert self.return_logits
        return self._step(inputrule, inputcoqview, past_key_values)


def strip_pad(tensor, pad_id=0):
    return [int(value) for value in tensor.tolist() if int(value) != int(pad_id)]


def load_shortest_test_row(task):
    task_dir = REPO_ROOT / "Utils" / "data" / task
    config = Dotdict(json.loads((task_dir / "config.json").read_text()))
    config.task = task
    config.mask_id = config.get("mask_id", 0)
    Dataset.args = config
    Dataset.PAD_token = config.mask_id
    with (task_dir / "test.pkl").open("rb") as handle:
        rows = pickle.load(handle)
    row_index = min(
        range(len(rows)),
        key=lambda index: len(rows[index]["rulelist"]) - len(rows[index].get("prefix", [])),
    )
    return config, row_index, rs_collate_fn_cutprefix([rows[row_index]])


def assert_decoder_history(calls, prefix, suffix):
    assert len(calls) == len(suffix), (len(calls), len(suffix))
    assert calls[0]["inputrule"].shape[0] == 1
    assert strip_pad(calls[0]["inputrule"][0]) == prefix
    assert calls[0]["had_cache"] is False
    for step in range(1, len(suffix)):
        assert calls[step]["inputrule"].tolist() == [[suffix[step - 1]]]
        assert calls[step]["had_cache"] is True


def check_java():
    config, row_index, batch = load_shortest_test_row(JAVA_TASK)
    rules = load_rules_for_task(JAVA_TASK)
    tokenizer = load_tokenizer_for_task(JAVA_TASK)
    prefix = strip_pad(batch["prefix"][0], config.mask_id)
    suffix = strip_pad(batch["res"][0], config.mask_id)
    model = ForcedGoldModel(suffix, len(rules), return_logits=True)

    beamsearch_coq.configure_runtime(rules, tokenizer_obj=tokenizer)
    original_open = getattr(beamsearch_coq, "open", None)
    original_makedirs = beamsearch_coq.os.makedirs
    original_runner = beamsearch_coq.test_coq_proof_with_timeout
    coq_checks = []
    beamsearch_coq.open = lambda *args, **kwargs: io.StringIO()
    beamsearch_coq.os.makedirs = lambda *args, **kwargs: None
    beamsearch_coq.test_coq_proof_with_timeout = lambda args: (
        coq_checks.append(args) or (True, "empty_context")
    )
    try:
        beam = beamsearch_coq.BeamSearch(
            1,
            rules,
            coqview_len=config.max_coqview_len,
            addCoqview=True,
            checkcoq=False,
            tokenizer_obj=tokenizer,
            candidate_multiplier=2,
            coq_workers=1,
            disable_tqdm=True,
        )
        result = beam.search(
            batch["nl"],
            model,
            max_len=len(suffix) + 1,
            offset=row_index,
            init_tokens=batch["prefix"],
        )
    finally:
        if original_open is None:
            del beamsearch_coq.open
        else:
            beamsearch_coq.open = original_open
        beamsearch_coq.os.makedirs = original_makedirs
        beamsearch_coq.test_coq_proof_with_timeout = original_runner

    assert_decoder_history(model.calls, prefix, suffix)
    assert all(call["inputcoqview"].shape == (1, 1, config.max_coqview_len) for call in model.calls)
    assert len(result) == 1 and len(result[0].final_set) == 1
    # One initial-prefix check plus one score-leading candidate per decoding
    # step (and at most one extra live continuation after the final program).
    # The eager implementation checked both top-k expansions at every step
    # despite beam size one and would make roughly twice as many calls here.
    assert len(coq_checks) <= len(suffix) + 2
    assert all(path for path, _timeout in coq_checks)
    assert all(
        Path(path).stem.endswith(f"_{os.getpid()}")
        for path, _timeout in coq_checks
    )
    return {
        "row_index": row_index,
        "prefix_len": len(prefix),
        "suffix_len": len(suffix),
        "decoder_calls": len(model.calls),
        "cache_reorders": len(model.cache.reorders),
        "coq_checks": len(coq_checks),
        "final_candidates": len(result[0].final_set),
    }


def check_sufu():
    config, row_index, batch = load_shortest_test_row(SUFU_TASK)
    rules = load_rules_for_task(SUFU_TASK)
    tokenizer = load_tokenizer_for_task(SUFU_TASK)
    prefix = strip_pad(batch["prefix"][0], config.mask_id)
    suffix = strip_pad(batch["res"][0], config.mask_id)
    model = ForcedGoldModel(suffix, len(rules), return_logits=True)

    beam = beamsearch_sufu.BeamSearch(
        1,
        rules,
        type_ctx_len=config.max_coqview_len,
        add_type_ctx=True,
        tokenizer_obj=tokenizer,
        candidate_multiplier=2,
        disable_tqdm=True,
    )
    result = beam.search(
        batch["nl"],
        model,
        max_len=len(suffix) + 1,
        offset=row_index,
        init_tokens=batch["prefix"],
    )

    assert_decoder_history(model.calls, prefix, suffix)
    for step, call in enumerate(model.calls):
        assert call["inputcoqview"].shape == (1, 1, config.max_coqview_len)
        assert torch.equal(call["inputcoqview"][0, 0], batch["coqview"][0, step])
    assert len(result) == 1 and len(result[0].final_set) == 1
    return {
        "row_index": row_index,
        "prefix_len": len(prefix),
        "suffix_len": len(suffix),
        "decoder_calls": len(model.calls),
        "coqview_steps_exact": len(model.calls),
        "cache_reorders": len(model.cache.reorders),
        "final_candidates": len(result[0].final_set),
    }


def test_java_forced_gold_history_and_lazy_coq_checks():
    check_java()


def test_sufu_forced_gold_history_and_context_alignment():
    check_sufu()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json_out", default="")
    args = parser.parse_args()
    result = {"java": check_java(), "sufu": check_sufu()}
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    if args.json_out:
        Path(args.json_out).write_text(rendered + "\n")


if __name__ == "__main__":
    main()
