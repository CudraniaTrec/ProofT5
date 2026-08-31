from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import time
from pathlib import Path

import numpy as np
import torch
from accelerate import Accelerator
from accelerate.utils import set_seed
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModelForCausalLM, AutoTokenizer


class JavaCompletionDataset(Dataset):
    def __init__(self, rows, tokenizer, max_length: int):
        self.examples = []
        self.max_length = int(max_length)
        for row in rows:
            prompt = row["prompt"]
            code = row["code"]
            # The 65 HumanEval training rows have a canonical full source whose
            # import order/formatting intentionally differs from the benchmark
            # prompt.  Treat the task as causal seq2seq (prompt -> complete
            # source), rather than silently dropping those rows or assuming a
            # string suffix that does not exist.
            prompt_ids = tokenizer.encode(prompt, add_special_tokens=False) + [
                tokenizer.eos_token_id
            ]
            completion_ids = tokenizer.encode(code, add_special_tokens=False)
            input_ids = prompt_ids + completion_ids + [tokenizer.eos_token_id]
            if len(input_ids) > self.max_length:
                raise ValueError(
                    f"training row {row['task_id']} has {len(input_ids)} tokens, "
                    f"above max_length={self.max_length}"
                )
            labels = [-100] * len(prompt_ids) + completion_ids + [tokenizer.eos_token_id]
            self.examples.append(
                {
                    "input_ids": input_ids,
                    "labels": labels,
                    "task_id": row["task_id"],
                    "is_distributed_padding": False,
                }
            )

    def pad_to_multiple(self, multiple: int) -> int:
        original = len(self.examples)
        while len(self.examples) % int(multiple):
            padding = dict(self.examples[-1])
            padding["is_distributed_padding"] = True
            self.examples.append(padding)
        return len(self.examples) - original

    def __len__(self):
        return len(self.examples)

    def __getitem__(self, index):
        return self.examples[index]


class CompletionCollator:
    def __init__(self, pad_token_id: int):
        self.pad_token_id = int(pad_token_id)

    def __call__(self, rows):
        width = max(len(row["input_ids"]) for row in rows)
        input_ids = []
        labels = []
        attention_mask = []
        for row in rows:
            padding = width - len(row["input_ids"])
            input_ids.append(row["input_ids"] + [self.pad_token_id] * padding)
            labels.append(row["labels"] + [-100] * padding)
            attention_mask.append([1] * len(row["input_ids"]) + [0] * padding)
        return {
            "input_ids": torch.tensor(input_ids, dtype=torch.long),
            "labels": torch.tensor(labels, dtype=torch.long),
            "attention_mask": torch.tensor(attention_mask, dtype=torch.long),
            "is_distributed_padding": torch.tensor(
                [row.get("is_distributed_padding", False) for row in rows],
                dtype=torch.bool,
            ),
        }


def read_rows(path: str, split_type: str):
    rows = json.loads(Path(path).read_text())
    return [row for row in rows if row.get("type") == split_type]


def append_jsonl(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def directory_fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    for child in sorted(item for item in path.rglob("*") if item.is_file()):
        digest.update(str(child.relative_to(path)).encode())
        digest.update(str(child.stat().st_size).encode())
        with child.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
    return digest.hexdigest()


def save_checkpoint(accelerator, model, tokenizer, output_root: Path, epoch: int):
    checkpoint = output_root / f"epoch{epoch}"
    accelerator.wait_for_everyone()
    if accelerator.is_main_process:
        checkpoint.mkdir(parents=True, exist_ok=False)
        unwrapped = accelerator.unwrap_model(model)
        unwrapped.save_pretrained(
            checkpoint,
            state_dict=accelerator.get_state_dict(model),
            safe_serialization=True,
        )
        tokenizer.save_pretrained(checkpoint)
        (checkpoint / "checkpoint_manifest.json").write_text(
            json.dumps({"epoch": epoch, "selection_status": "unselected"}, indent=2)
            + "\n"
        )
    accelerator.wait_for_everyone()


def train(args):
    accelerator = Accelerator(mixed_precision="bf16")
    set_seed(args.seed, device_specific=True)
    tokenizer = AutoTokenizer.from_pretrained(
        args.model, local_files_only=True, padding_side="right"
    )
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    rows = read_rows(args.dataset_json, "train")
    dataset = JavaCompletionDataset(rows, tokenizer, args.max_length)
    padding_rows = dataset.pad_to_multiple(
        accelerator.num_processes * args.batch_size
    )
    loader_generator = torch.Generator().manual_seed(args.seed)
    loader = DataLoader(
        dataset,
        batch_size=args.batch_size,
        shuffle=True,
        generator=loader_generator,
        collate_fn=CompletionCollator(tokenizer.pad_token_id),
        num_workers=args.workers,
        pin_memory=True,
    )
    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        local_files_only=True,
        dtype=torch.bfloat16,
    )
    model.config.use_cache = False
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=args.learning_rate, weight_decay=args.weight_decay
    )
    model, optimizer, loader = accelerator.prepare(model, optimizer, loader)
    output_root = Path(args.output_dir)
    metrics_path = Path(args.metrics_file)
    if accelerator.is_main_process:
        if output_root.exists() or metrics_path.exists():
            raise FileExistsError("refusing to overwrite an existing Qwen plain run")
        output_root.mkdir(parents=True)
        append_jsonl(
            metrics_path,
            {
                "event": "configuration",
                "base_model": args.model,
                "train_rows": len(rows),
                "epochs": args.epochs,
                "save_epochs": args.save_epochs,
                "learning_rate": args.learning_rate,
                "world_size": accelerator.num_processes,
                "distributed_zero_loss_padding_rows": padding_rows,
                "seed": args.seed,
                "target": "complete Java source after a prompt/EOS boundary",
            },
        )
    accelerator.wait_for_everyone()
    save_epochs = {int(value) for value in args.save_epochs.split(",") if value}
    for epoch_index in range(args.epochs):
        model.train()
        epoch_loss_sum = torch.zeros(1, device=accelerator.device, dtype=torch.float64)
        epoch_tokens = torch.zeros(1, device=accelerator.device, dtype=torch.long)
        started = time.time()
        for batch in loader:
            optimizer.zero_grad(set_to_none=True)
            padding_mask = batch.pop("is_distributed_padding")
            output = model(**batch)
            active = (
                batch["labels"].ne(-100).sum(dim=1)
                * (~padding_mask).to(dtype=torch.long)
            ).sum().reshape(1)
            gathered_active = accelerator.gather(active)
            global_active = gathered_active.sum().clamp_min(1)
            backward_scale = (
                accelerator.num_processes * active.to(output.loss.dtype) / global_active
            )
            accelerator.backward(output.loss * backward_scale)
            optimizer.step()
            epoch_loss_sum += output.loss.detach().double() * active.double()
            epoch_tokens += active
        gathered_loss_sum = accelerator.gather(epoch_loss_sum).sum().item()
        gathered_tokens = int(accelerator.gather(epoch_tokens).sum().item())
        epoch_number = epoch_index + 1
        if accelerator.is_main_process:
            append_jsonl(
                metrics_path,
                {
                    "event": "epoch",
                    "epoch": epoch_number,
                    "global_token_loss": gathered_loss_sum / max(1, gathered_tokens),
                    "active_target_tokens": gathered_tokens,
                    "wall_seconds": time.time() - started,
                },
            )
        if epoch_number in save_epochs:
            save_checkpoint(accelerator, model, tokenizer, output_root, epoch_number)
    if accelerator.is_main_process:
        manifest = {
            "status": "complete",
            "model": args.model,
            "dataset_json": args.dataset_json,
            "train_rows": len(rows),
            "checkpoint_epochs": sorted(save_epochs),
            "checkpoint_fingerprints": {
                f"epoch{epoch}": directory_fingerprint(output_root / f"epoch{epoch}")
                for epoch in sorted(save_epochs)
            },
        }
        (output_root / "run_manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n"
        )


@torch.no_grad()
def evaluate(args):
    accelerator = Accelerator(mixed_precision="bf16")
    tokenizer = AutoTokenizer.from_pretrained(
        args.checkpoint, local_files_only=True, padding_side="left"
    )
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        args.checkpoint, local_files_only=True, dtype=torch.bfloat16
    ).to(accelerator.device)
    model.eval()
    rows = json.loads(Path(args.dataset_json).read_text())
    output_dir = Path(args.output_dir)
    if accelerator.is_main_process:
        output_dir.mkdir(parents=True, exist_ok=False)
    accelerator.wait_for_everyone()
    indices = list(range(accelerator.process_index, len(rows), accelerator.num_processes))
    for index in indices:
        row = rows[index]
        prompt_ids = tokenizer.encode(row["prompt"], add_special_tokens=False) + [
            tokenizer.eos_token_id
        ]
        encoded = {
            "input_ids": torch.tensor([prompt_ids], device=accelerator.device),
            "attention_mask": torch.ones(
                (1, len(prompt_ids)), device=accelerator.device, dtype=torch.long
            ),
        }
        outputs = model.generate(
            **encoded,
            do_sample=False,
            num_beams=args.beams,
            num_return_sequences=args.beams,
            max_new_tokens=args.max_new_tokens,
            length_penalty=args.length_penalty,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )
        prompt_width = encoded["input_ids"].size(1)
        for rank, output in enumerate(outputs):
            completion = tokenizer.decode(
                output[prompt_width:], skip_special_tokens=True
            )
            (output_dir / f"{index}_{rank}.txt").write_text(
                completion
            )
    accelerator.wait_for_everyone()
    if accelerator.is_main_process:
        missing = [
            f"{index}_{rank}.txt"
            for index in range(len(rows))
            for rank in range(args.beams)
            if not (output_dir / f"{index}_{rank}.txt").is_file()
        ]
        if missing:
            raise RuntimeError(f"incomplete generation: {missing[:10]}")
        (output_dir / "baseline_manifest.json").write_text(
            json.dumps(
                {
                    "method": "qwen_plain_java_beam",
                    "checkpoint": args.checkpoint,
                    "checkpoint_fingerprint": directory_fingerprint(
                        Path(args.checkpoint)
                    ),
                    "problems": len(rows),
                    "beams": args.beams,
                    "max_new_tokens": args.max_new_tokens,
                    "length_penalty": args.length_penalty,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )


def parse_args():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="action", required=True)
    train_parser = subparsers.add_parser("train")
    train_parser.add_argument("--model", default="Utils/models/Qwen2.5-3B")
    train_parser.add_argument(
        "--dataset_json", default="t5_llm/data/java_mbjp_humaneval_half_train_t5.json"
    )
    train_parser.add_argument("--output_dir", required=True)
    train_parser.add_argument("--metrics_file", required=True)
    train_parser.add_argument("--epochs", type=int, default=20)
    train_parser.add_argument("--save_epochs", default="5,10,15,20")
    train_parser.add_argument("--batch_size", type=int, default=1)
    train_parser.add_argument("--learning_rate", type=float, default=2e-5)
    train_parser.add_argument("--weight_decay", type=float, default=0.0)
    train_parser.add_argument("--max_length", type=int, default=1536)
    train_parser.add_argument("--workers", type=int, default=2)
    train_parser.add_argument("--seed", type=int, default=273567)
    eval_parser = subparsers.add_parser("eval")
    eval_parser.add_argument("--checkpoint", required=True)
    eval_parser.add_argument(
        "--dataset_json", default="t5_llm/data/java_mbjp_original_test_t5.json"
    )
    eval_parser.add_argument("--output_dir", required=True)
    eval_parser.add_argument("--beams", type=int, default=10)
    eval_parser.add_argument("--max_new_tokens", type=int, default=1024)
    eval_parser.add_argument("--length_penalty", type=float, default=0.1)
    return parser.parse_args()


if __name__ == "__main__":
    parsed = parse_args()
    if parsed.action == "train":
        train(parsed)
    else:
        evaluate(parsed)
