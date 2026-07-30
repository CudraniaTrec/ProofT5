import argparse
import datetime
import json
import os
import pickle
import random
import time

import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset, SequentialSampler
from tqdm import tqdm
from transformers import AutoModelForSeq2SeqLM, AutoProcessor, AutoTokenizer

try:
    import swanlab
except Exception:  # pragma: no cover - swanlab is optional for smoke tests.
    swanlab = None

from evaluator.CodeBLEU.calc_code_bleu import get_codebleu


SEED = 273567
SCRIPT_DIR = os.path.abspath(os.path.dirname(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))


def set_seed(seed=SEED):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)


class TextCodec:
    def __init__(self, model_path, local_files_only=True):
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(
                model_path,
                local_files_only=local_files_only,
                trust_remote_code=True,
            )
            self.processor = None
        except Exception:
            self.processor = AutoProcessor.from_pretrained(
                model_path,
                local_files_only=local_files_only,
                trust_remote_code=True,
            )
            self.tokenizer = self.processor.tokenizer

    @property
    def pad_token_id(self):
        return self.tokenizer.pad_token_id

    @property
    def eos_token_id(self):
        return self.tokenizer.eos_token_id

    def encode(self, text, max_length, padding=False):
        return self.tokenizer(
            text,
            return_tensors="pt",
            max_length=max_length,
            truncation=True,
            padding="max_length" if padding else False,
        )["input_ids"][0]

    def batch_decode(self, ids, skip_special_tokens=True):
        return self.tokenizer.batch_decode(ids, skip_special_tokens=skip_special_tokens)


class CodeDataset(Dataset):
    def __init__(self, data, codec, max_input_length=1024, max_output_length=1024):
        self.inputs = []
        self.labels = []
        for example in data:
            code = example["code"] if "code" in example else example["prompt"] + example["canonical_solution"]
            prompt = example["prompt"]
            input_ids = codec.encode(prompt, max_input_length, padding=True)
            label_ids = codec.encode(code, max_output_length, padding=False).tolist()
            if not label_ids or label_ids[-1] != codec.eos_token_id:
                label_ids.append(codec.eos_token_id)
            if len(label_ids) > max_output_length:
                label_ids = label_ids[: max_output_length - 1] + [codec.eos_token_id]
            pad_len = max_output_length - len(label_ids)
            labels = label_ids + [codec.pad_token_id] * max(0, pad_len)
            labels = [tok if tok != codec.pad_token_id else -100 for tok in labels]
            self.inputs.append(input_ids)
            self.labels.append(torch.tensor(labels))

    def __len__(self):
        return len(self.inputs)

    def __getitem__(self, idx):
        return {"input": self.inputs[idx], "labels": self.labels[idx]}


def dataset_path(dataset_name):
    paths = {
        "mbjp": os.path.join(SCRIPT_DIR, "data", "mbjp_t5.json"),
        "sufu": os.path.join(SCRIPT_DIR, "data", "sufu_t5.json"),
        "humaneval": os.path.join(SCRIPT_DIR, "data", "humaneval_t5.json"),
    }
    if dataset_name not in paths:
        raise ValueError(f"Unsupported dataset: {dataset_name}")
    return paths[dataset_name]


def reference_code(dataset_name, rows):
    if dataset_name == "humaneval":
        return [row["code"] for row in rows]
    if dataset_name == "mbjp":
        return [row["prompt"] + row["canonical_solution"] for row in rows]
    if dataset_name == "sufu":
        return [row["code"] for row in rows]
    raise ValueError(f"Unsupported dataset: {dataset_name}")


def split_rows(rows):
    return (
        [row for row in rows if row["type"] == "train"],
        [row for row in rows if row["type"] == "valid"],
        [row for row in rows if row["type"] == "test"],
    )


def train_epoch(model, dataset, optimizer, device, batch_size):
    model.train()
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)
    total_loss = 0.0
    for batch in loader:
        optimizer.zero_grad()
        input_ids = batch["input"].to(device)
        labels = batch["labels"].to(device)
        attention_mask = input_ids.ne(0)
        loss = model(input_ids=input_ids, attention_mask=attention_mask, labels=labels).loss
        loss.backward()
        optimizer.step()
        total_loss += loss.item()
    return total_loss / max(1, len(loader))


@torch.no_grad()
def generate_outputs(model, dataset, refs, codec, dataset_name, device, batch_size, topk, output_path=None, max_length=1024):
    model.eval()
    loader = DataLoader(dataset, sampler=SequentialSampler(dataset), batch_size=batch_size)
    predictions = []
    for batch in tqdm(loader, desc=f"generate top{topk}", leave=False):
        input_ids = batch["input"].to(device)
        attention_mask = input_ids.ne(0)
        preds = model.generate(
            input_ids=input_ids,
            attention_mask=attention_mask,
            max_length=max_length,
            num_beams=topk,
            num_return_sequences=topk,
            eos_token_id=codec.eos_token_id,
            pad_token_id=codec.pad_token_id,
            early_stopping=True,
        )
        predictions.extend(list(preds.cpu().numpy()))

    pred_texts = codec.batch_decode(predictions, skip_special_tokens=True)
    codebleu_lang = "java"
    codebleu = get_codebleu(
        [ref.strip() for ref in refs],
        [pred.strip() for pred in pred_texts[::topk]],
        codebleu_lang,
    )
    if output_path:
        output_dir = os.path.join(REPO_ROOT, "Utils", "output", output_path)
        os.makedirs(output_dir, exist_ok=True)
        for num in range(len(pred_texts) // topk):
            for i in range(topk):
                with open(os.path.join(output_dir, f"{num}_{i}.txt"), "w") as f:
                    f.write(pred_texts[num * topk + i])
        print(f"Saved predictions to {output_dir}")
    model.train()
    return pred_texts, codebleu


def dump_raw_splits(task_name, train_rows, valid_rows, test_rows):
    target = os.path.join(REPO_ROOT, "Utils", "data", task_name)
    os.makedirs(target, exist_ok=True)
    for name, rows in [("train", train_rows), ("valid", valid_rows), ("test", test_rows)]:
        with open(os.path.join(target, f"{name}.pkl"), "wb") as f:
            pickle.dump(rows, f)


def finetune(args):
    set_seed()
    model_path = args.model_path
    model_alias = args.model_alias
    task_name = f"{model_alias}_{args.dataset}"
    date = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    codec = TextCodec(model_path, local_files_only=args.local_files_only)
    rows = json.load(open(dataset_path(args.dataset), "r"))
    train_rows, valid_rows, test_rows = split_rows(rows)
    if args.dataset == "sufu" and not valid_rows:
        valid_rows = test_rows
    dump_raw_splits(task_name, train_rows, valid_rows, test_rows)

    print(f"Task: {task_name}")
    print(f"Train/valid/test: {len(train_rows)}/{len(valid_rows)}/{len(test_rows)}")
    print(f"Tokenizer size: {len(codec.tokenizer)}")
    if args.dry_run:
        return

    load_path = args.checkpoint_path if args.generate_only and args.checkpoint_path else model_path
    torch_dtype = torch.bfloat16 if args.bf16 else "auto"
    model = AutoModelForSeq2SeqLM.from_pretrained(
        load_path,
        local_files_only=args.local_files_only,
        trust_remote_code=True,
        torch_dtype=torch_dtype,
    )

    train_set = CodeDataset(train_rows, codec, args.max_input_length, args.max_output_length)
    valid_set = CodeDataset(valid_rows, codec, args.max_input_length, args.max_output_length)
    test_set = CodeDataset(test_rows, codec, args.max_input_length, args.max_output_length)
    valid_refs = reference_code(args.dataset, valid_rows)
    test_refs = reference_code(args.dataset, test_rows)

    device = "cuda" if args.cuda == -1 else f"cuda:{args.cuda}"
    model = model.to(device)
    if args.generate_only:
        output_subdir = args.output_subdir or f"{date}/generate_only"
        generate_outputs(
            model,
            test_set,
            test_refs,
            codec,
            args.dataset,
            device,
            args.eval_batch_size,
            args.topk,
            output_path=f"{task_name}_test_ans/{output_subdir}",
            max_length=args.generation_max_length,
        )
        return

    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)

    log = None
    if swanlab is not None and not args.no_swanlab:
        log = swanlab.init(project="finetune_t5gemma2", experiment_name=f"{task_name}_{date}")

    best_score = 0.0
    patience = 0
    for epoch in range(args.max_epochs + 1):
        loss = train_epoch(model, train_set, optimizer, device, args.batch_size)
        print(f"{task_name} epoch {epoch}: loss={loss:.6f}")
        if log:
            log.log({"loss": loss})

        if epoch >= args.warmup_epochs and epoch % args.eval_step == 0:
            _, valid_score = generate_outputs(
                model,
                valid_set,
                valid_refs,
                codec,
                args.dataset,
                device,
                args.eval_batch_size,
                1,
                max_length=args.generation_max_length,
            )
            test_score = None
            if not args.skip_test_during_eval:
                _, test_score = generate_outputs(
                    model,
                    test_set,
                    test_refs,
                    codec,
                    args.dataset,
                    device,
                    args.eval_batch_size,
                    args.topk,
                    output_path=f"{task_name}_test_ans/{date}/{epoch}",
                    max_length=args.generation_max_length,
                )
            print(f"{task_name} epoch {epoch}: valid_codebleu={valid_score}, test_codebleu={test_score}")
            if log:
                log.log({"valid_codebleu": valid_score, "test_codebleu": test_score})
            model.save_pretrained(os.path.join(SCRIPT_DIR, "models", task_name, date, f"epoch_{epoch}"))
            if valid_score > best_score:
                best_score = valid_score
                patience = 0
                model.save_pretrained(os.path.join(SCRIPT_DIR, "models", task_name, date, "best"))
            else:
                patience += 1
                if patience >= args.patience:
                    break
            torch.cuda.empty_cache()

    model.save_pretrained(os.path.join(SCRIPT_DIR, "models", task_name))
    generate_outputs(
        model,
        test_set,
        test_refs,
        codec,
        args.dataset,
        device,
        args.eval_batch_size,
        args.topk,
        output_path=f"{task_name}_test_ans/{date}/final",
        max_length=args.generation_max_length,
    )
    if log:
        log.finish()


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_path", default=os.path.join(REPO_ROOT, "Utils", "models", "t5gemma-2-1b-1b"))
    parser.add_argument("--model_alias", default="t5gemma2-2b")
    parser.add_argument("--dataset", choices=["sufu", "mbjp", "humaneval"], required=True)
    parser.add_argument("--cuda", type=int, default=0)
    parser.add_argument("--batch_size", type=int, default=1)
    parser.add_argument("--eval_batch_size", type=int, default=1)
    parser.add_argument("--lr", type=float, default=5e-5)
    parser.add_argument("--weight_decay", type=float, default=1e-2)
    parser.add_argument("--warmup_epochs", type=int, default=5)
    parser.add_argument("--eval_step", type=int, default=5)
    parser.add_argument("--max_epochs", type=int, default=100)
    parser.add_argument("--patience", type=int, default=3)
    parser.add_argument("--topk", type=int, default=10)
    parser.add_argument("--generation_max_length", type=int, default=1024)
    parser.add_argument("--skip_test_during_eval", action="store_true")
    parser.add_argument("--max_input_length", type=int, default=1024)
    parser.add_argument("--max_output_length", type=int, default=1024)
    parser.add_argument("--bf16", action="store_true")
    parser.add_argument("--no_swanlab", action="store_true")
    parser.add_argument("--dry_run", action="store_true")
    parser.add_argument("--generate_only", action="store_true")
    parser.add_argument("--checkpoint_path", default="")
    parser.add_argument("--output_subdir", default="")
    parser.add_argument("--local_files_only", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args()


if __name__ == "__main__":
    finetune(parse_args())
