"""Decode-variant candidate generator for the plain T5Gemma2-2B baseline.

Variants (selected on the 32-task validation holdout, never on the 16-task test):
  beam10      : published protocol (HF beam, beam 10, penalty 1.0)
  sample10    : 10 i.i.d. samples, temperature 0.8, top_p 0.95
  few3_beam10 : 3-shot prompt (three fixed train-split exemplars) + beam 10

Writes candidates as {idx}_{k}.txt compatible with score_java_no_write.py.
"""

import argparse
import json
import os
import pickle
import sys

import torch
from torch.utils.data import DataLoader, SequentialSampler

sys.path.insert(0, "t5_llm")
from finetune_t5gemma2 import TextCodec, set_seed  # noqa: E402

from transformers import AutoModelForSeq2SeqLM  # noqa: E402

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class PromptDataset(torch.utils.data.Dataset):
    def __init__(self, rows, codec, max_input_length, prompts):
        self.inputs = []
        for prompt in prompts:
            self.inputs.append(codec.encode(prompt, max_input_length, padding=True))

    def __len__(self):
        return len(self.inputs)

    def __getitem__(self, idx):
        return {"input": self.inputs[idx]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model_path", required=True)
    ap.add_argument("--tokenizer_path", default=os.path.join(REPO, "Utils", "models", "t5gemma-2-1b-1b"))
    ap.add_argument("--data_pkl", required=True, help="pickle with rows (prompt field used)")
    ap.add_argument("--prompts_json", required=True, help="json list of full input prompts, aligned with rows")
    ap.add_argument("--output_dir", required=True)
    ap.add_argument("--variant", choices=["beam10", "sample10", "few3_beam10"], required=True)
    ap.add_argument("--topk", type=int, default=10)
    ap.add_argument("--max_input_length", type=int, default=2048)
    ap.add_argument("--max_output_length", type=int, default=1024)
    ap.add_argument("--cuda", type=int, default=0)
    args = ap.parse_args()

    set_seed()
    rows = pickle.load(open(args.data_pkl, "rb"))
    prompts = json.load(open(args.prompts_json))
    assert len(rows) == len(prompts)
    codec = TextCodec(args.tokenizer_path)
    model = AutoModelForSeq2SeqLM.from_pretrained(args.model_path, local_files_only=True)
    device = f"cuda:{args.cuda}"
    model.eval().to(device)
    if "bf16" in args.variant or True:
        model = model.to(torch.bfloat16)

    ds = PromptDataset(rows, codec, args.max_input_length, prompts)
    loader = DataLoader(ds, sampler=SequentialSampler(ds), batch_size=4)
    os.makedirs(args.output_dir, exist_ok=True)

    gen_kwargs = dict(max_length=args.max_output_length, num_return_sequences=args.topk,
                      eos_token_id=codec.eos_token_id, pad_token_id=codec.pad_token_id)
    if args.variant in ("beam10", "few3_beam10"):
        gen_kwargs.update(num_beams=args.topk, early_stopping=True, length_penalty=1.0)
    else:  # sample10
        gen_kwargs.update(do_sample=True, num_beams=1, temperature=0.8, top_p=0.95)

    out_rows = []
    ptr = 0
    for batch in loader:
        input_ids = batch["input"].to(device)
        attention_mask = input_ids.ne(codec.pad_token_id)
        with torch.no_grad():
            preds = model.generate(input_ids=input_ids, attention_mask=attention_mask, **gen_kwargs)
        texts = codec.batch_decode(preds, skip_special_tokens=True)
        for b in range(input_ids.size(0)):
            idx = ptr + b
            for k in range(args.topk):
                with open(os.path.join(args.output_dir, f"{idx}_{k}.txt"), "w") as f:
                    f.write(texts[b * args.topk + k])
        ptr += input_ids.size(0)
    print(f"saved {ptr} x {args.topk} candidates to {args.output_dir}")


if __name__ == "__main__":
    main()
