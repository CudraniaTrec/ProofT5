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
    def __init__(
        self,
        data,
        codec,
        max_input_length=1024,
        max_output_length=1024,
        target_mode="full",
    ):
        self.inputs = []
        self.labels = []
        for example in data:
            if target_mode == "solution":
                if "canonical_solution" not in example:
                    raise ValueError(
                        "solution target mode requires canonical_solution in every row"
                    )
                code = example["canonical_solution"]
            elif target_mode == "full":
                code = (
                    example["code"]
                    if "code" in example
                    else example["prompt"] + example["canonical_solution"]
                )
            else:
                raise ValueError(f"unsupported target mode: {target_mode}")
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
        "java_expanded_train": os.path.join(
            SCRIPT_DIR, "data", "java_mbjp_humaneval_half_train_t5.json"
        ),
        "java_mbjp_test": os.path.join(
            SCRIPT_DIR, "data", "java_mbjp_original_test_t5.json"
        ),
        "java_humaneval_test": os.path.join(
            SCRIPT_DIR, "data", "java_humaneval_half_test_t5.json"
        ),
        "sufu_expanded_train": os.path.join(
            SCRIPT_DIR, "data", "sufu_original_synthetic_half_train_t5.json"
        ),
        "sufu_original_test": os.path.join(
            SCRIPT_DIR, "data", "sufu_original_test_t5.json"
        ),
        "sufu_synthetic_test": os.path.join(
            SCRIPT_DIR, "data", "sufu_synthetic_half_test_t5.json"
        ),
    }
    if dataset_name not in paths:
        raise ValueError(f"Unsupported dataset: {dataset_name}")
    return paths[dataset_name]


def reference_code(dataset_name, rows):
    if all("code" in row for row in rows):
        return [row["code"] for row in rows]
    if dataset_name == "humaneval":
        return [row["code"] for row in rows]
    if dataset_name == "mbjp":
        return [row["prompt"] + row["canonical_solution"] for row in rows]
    if dataset_name == "sufu":
        return [row["code"] for row in rows]
    raise ValueError(f"Unsupported dataset: {dataset_name}")


def split_rows(rows, include_debug=False):
    train_types = {"train", "debug"} if include_debug else {"train"}
    return (
        [row for row in rows if row["type"] in train_types],
        [row for row in rows if row["type"] == "valid"],
        [row for row in rows if row["type"] == "test"],
    )


def train_epoch(
    model,
    dataset,
    optimizer,
    device,
    batch_size,
    step_checkpoint_every=0,
    step_checkpoint_max_step=0,
    step_checkpoint_dir="",
    epoch=0,
):
    model.train()
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)
    total_loss_sum = 0.0
    total_active_target_tokens = 0
    completed_batches = 0
    for step, batch in enumerate(loader, start=1):
        optimizer.zero_grad()
        input_ids = batch["input"].to(device)
        labels = batch["labels"].to(device)
        attention_mask = input_ids.ne(0)
        loss = model(input_ids=input_ids, attention_mask=attention_mask, labels=labels).loss
        loss.backward()
        optimizer.step()
        active_target_tokens = int(labels.ne(-100).sum().item())
        if active_target_tokens <= 0:
            raise RuntimeError(f"epoch {epoch} step {step} has no active target tokens")
        total_loss_sum += float(loss.item()) * active_target_tokens
        total_active_target_tokens += active_target_tokens
        completed_batches += 1
        if (
            step_checkpoint_every > 0
            and step % step_checkpoint_every == 0
            and (
                step_checkpoint_max_step <= 0
                or step <= step_checkpoint_max_step
            )
        ):
            model.save_pretrained(
                os.path.join(
                    step_checkpoint_dir, f"epoch_{epoch}_step_{step}"
                )
            )
    if completed_batches != len(loader) or total_active_target_tokens <= 0:
        raise RuntimeError(
            f"epoch {epoch} is incomplete: batches={completed_batches}/{len(loader)}, "
            f"active_target_tokens={total_active_target_tokens}"
        )
    return (
        total_loss_sum / total_active_target_tokens,
        total_active_target_tokens,
        completed_batches,
    )


@torch.no_grad()
def generate_outputs(
    model,
    dataset,
    refs,
    codec,
    dataset_name,
    device,
    batch_size,
    topk,
    output_path=None,
    max_length=1024,
    length_penalty=1.0,
    exact_prefixes=None,
):
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
            length_penalty=length_penalty,
        )
        predictions.extend(list(preds.cpu().numpy()))

    pred_texts = codec.batch_decode(predictions, skip_special_tokens=True)
    if exact_prefixes is not None:
        if len(exact_prefixes) * topk != len(pred_texts):
            raise RuntimeError(
                "exact-prefix count does not match generated candidate count"
            )
        pred_texts = [
            exact_prefixes[index // topk] + prediction
            for index, prediction in enumerate(pred_texts)
        ]
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
    if args.preserve_input_prefix and args.target_mode != "solution":
        raise ValueError(
            "preserve_input_prefix is only valid with target_mode=solution"
        )
    model_path = args.model_path
    model_alias = args.model_alias
    task_name = args.task_name or f"{model_alias}_{args.dataset}"
    if args.include_debug:
        task_name += "_debug"
    date = args.run_name or datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    codec = TextCodec(
        args.tokenizer_path or model_path,
        local_files_only=args.local_files_only,
    )
    data_path = args.dataset_file or dataset_path(args.dataset)
    rows = json.load(open(data_path, "r"))
    if args.generate_only and args.generate_all_rows:
        train_rows, valid_rows, test_rows = [], [], rows
    else:
        train_rows, valid_rows, test_rows = split_rows(
            rows,
            include_debug=args.include_debug,
        )
    overlap_rows = sum(bool(row.get("debug_overlap")) for row in train_rows)
    if overlap_rows:
        print(
            "WARNING: debug-only training data contains "
            f"{overlap_rows} rows copied from a test benchmark."
        )
    dump_raw_splits(task_name, train_rows, valid_rows, test_rows)

    print(f"Task: {task_name}")
    print(f"Train/valid/test: {len(train_rows)}/{len(valid_rows)}/{len(test_rows)}")
    print(f"Tokenizer size: {len(codec.tokenizer)}")
    if args.dry_run:
        return
    if not args.generate_only and not train_rows:
        raise ValueError("training requires a non-empty train split")

    load_path = args.checkpoint_path if args.generate_only and args.checkpoint_path else model_path
    torch_dtype = torch.bfloat16 if args.bf16 else "auto"
    model = AutoModelForSeq2SeqLM.from_pretrained(
        load_path,
        local_files_only=args.local_files_only,
        trust_remote_code=True,
        torch_dtype=torch_dtype,
    )

    train_set = CodeDataset(
        train_rows,
        codec,
        args.max_input_length,
        args.max_output_length,
        target_mode=args.target_mode,
    )
    valid_set = CodeDataset(
        valid_rows,
        codec,
        args.max_input_length,
        args.max_output_length,
        target_mode=args.target_mode,
    )
    test_set = CodeDataset(
        test_rows,
        codec,
        args.max_input_length,
        args.max_output_length,
        target_mode=args.target_mode,
    )
    valid_refs = reference_code(args.dataset, valid_rows)
    test_refs = reference_code(args.dataset, test_rows)

    device = "cuda" if args.cuda == -1 else f"cuda:{args.cuda}"
    model = model.to(device)
    if args.generate_only:
        if not test_rows:
            raise ValueError("generate_only requires a non-empty test split")
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
            length_penalty=args.generation_length_penalty,
            exact_prefixes=(
                [row["prompt"] for row in test_rows]
                if args.preserve_input_prefix else None
            ),
        )
        return

    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)

    log = None
    if swanlab is not None and not args.no_swanlab:
        log = swanlab.init(project="finetune_t5gemma2", experiment_name=f"{task_name}_{date}")

    best_score = 0.0
    patience = 0
    step_checkpoint_epochs = {
        int(value)
        for value in args.step_checkpoint_epochs.split(",")
        if value.strip()
    }
    for epoch in range(args.max_epochs + 1):
        loss, active_target_tokens, completed_batches = train_epoch(
            model,
            train_set,
            optimizer,
            device,
            args.batch_size,
            step_checkpoint_every=(
                args.checkpoint_every_steps
                if epoch in step_checkpoint_epochs
                else 0
            ),
            step_checkpoint_max_step=args.step_checkpoint_max_step,
            step_checkpoint_dir=os.path.join(
                SCRIPT_DIR, "models", task_name, date
            ),
            epoch=epoch,
        )
        print(
            f"{task_name} epoch {epoch}: "
            f"active_target_tokens={active_target_tokens} batches={completed_batches}"
        )
        print(f"{task_name} epoch {epoch}: loss={loss:.12g}")
        if log:
            log.log({"loss": loss})

        checkpoint_saved = False
        if (
            args.checkpoint_every_epochs > 0
            and epoch >= args.checkpoint_start_epoch
            and epoch % args.checkpoint_every_epochs == 0
        ):
            model.save_pretrained(
                os.path.join(SCRIPT_DIR, "models", task_name, date, f"epoch_{epoch}")
            )
            checkpoint_saved = True

        if valid_rows and epoch >= args.warmup_epochs and epoch % args.eval_step == 0:
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
                exact_prefixes=(
                    [row["prompt"] for row in valid_rows]
                    if args.preserve_input_prefix else None
                ),
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
                    exact_prefixes=(
                        [row["prompt"] for row in test_rows]
                        if args.preserve_input_prefix else None
                    ),
                )
            print(f"{task_name} epoch {epoch}: valid_codebleu={valid_score}, test_codebleu={test_score}")
            if log:
                log.log({"valid_codebleu": valid_score, "test_codebleu": test_score})
            if not checkpoint_saved:
                model.save_pretrained(
                    os.path.join(
                        SCRIPT_DIR, "models", task_name, date, f"epoch_{epoch}"
                    )
                )
            if valid_score > best_score:
                best_score = valid_score
                patience = 0
                model.save_pretrained(os.path.join(SCRIPT_DIR, "models", task_name, date, "best"))
            else:
                patience += 1
                if patience >= args.patience:
                    break
            torch.cuda.empty_cache()

    if not args.skip_root_save:
        model.save_pretrained(os.path.join(SCRIPT_DIR, "models", task_name))
    if test_rows and not args.skip_final_generation:
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
            exact_prefixes=(
                [row["prompt"] for row in test_rows]
                if args.preserve_input_prefix else None
            ),
        )
    if log:
        log.finish()


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_path", default=os.path.join(REPO_ROOT, "Utils", "models", "t5gemma-2-1b-1b"))
    parser.add_argument(
        "--tokenizer_path",
        default="",
        help="Optional tokenizer/processor source when model_path is a weight-only checkpoint.",
    )
    parser.add_argument("--model_alias", default="t5gemma2-2b")
    parser.add_argument(
        "--dataset",
        choices=[
            "sufu",
            "mbjp",
            "humaneval",
            "java_expanded_train",
            "java_mbjp_test",
            "java_humaneval_test",
            "sufu_expanded_train",
            "sufu_original_test",
            "sufu_synthetic_test",
        ],
        required=True,
    )
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
    parser.add_argument("--generation_length_penalty", type=float, default=1.0)
    parser.add_argument(
        "--target_mode",
        choices=["full", "solution"],
        default="full",
        help="Train/decode either the complete source file or only canonical_solution.",
    )
    parser.add_argument(
        "--preserve_input_prefix",
        action="store_true",
        help=(
            "Prepend each audited input prompt to generated solution-only candidates "
            "before saving and scoring."
        ),
    )
    parser.add_argument("--skip_test_during_eval", action="store_true")
    parser.add_argument("--max_input_length", type=int, default=1024)
    parser.add_argument("--max_output_length", type=int, default=1024)
    parser.add_argument("--bf16", action="store_true")
    parser.add_argument("--no_swanlab", action="store_true")
    parser.add_argument("--include_debug", action="store_true")
    parser.add_argument("--dry_run", action="store_true")
    parser.add_argument("--generate_only", action="store_true")
    parser.add_argument("--checkpoint_path", default="")
    parser.add_argument("--output_subdir", default="")
    parser.add_argument("--dataset_file", default="")
    parser.add_argument("--task_name", default="")
    parser.add_argument("--generate_all_rows", action="store_true")
    parser.add_argument("--run_name", default="")
    parser.add_argument("--checkpoint_every_epochs", type=int, default=0)
    parser.add_argument("--checkpoint_start_epoch", type=int, default=0)
    parser.add_argument("--checkpoint_every_steps", type=int, default=0)
    parser.add_argument("--step_checkpoint_max_step", type=int, default=0)
    parser.add_argument("--step_checkpoint_epochs", default="")
    parser.add_argument("--skip_root_save", action="store_true")
    parser.add_argument("--skip_final_generation", action="store_true")
    parser.add_argument("--local_files_only", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args()


if __name__ == "__main__":
    finetune(parse_args())
