import torch
import atexit
from contextlib import nullcontext
try:
    import swanlab
except Exception:
    swanlab = None
from torch import optim
from accelerate import Accelerator
from accelerate.utils import DistributedDataParallelKwargs, InitProcessGroupKwargs
from tqdm import tqdm, trange
import numpy as np
import os, sys, json, random, time, pickle, shutil
sys.setrecursionlimit(500000000)
import argparse, traceback, beeprint
from datetime import timedelta, datetime
from Utils.evaluator.CodeBLEU import calc_code_bleu

from Dataset import SumDataset, ChunkedRandomSampler, rs_collate_fn, rs_collate_fn_cutprefix
from Model import MyT5, MyT5withCoq1, MyT5withCoq2
try:
    from ModelT5Gemma2 import MyT5Gemma2, MyT5Gemma2withCoq1
except Exception:
    MyT5Gemma2 = MyT5Gemma2withCoq1 = None
try:
    from ModelQwenCausalDsl import MyQwenCausalDsl
except Exception:
    MyQwenCausalDsl = None
try:
    from ModelCodeGemmaCausalDsl import MyCodeGemmaCausalDsl
except Exception:
    MyCodeGemmaCausalDsl = None
BeamSearch = BeamSearchCoq = BeamSearchDsl = BeamSearchSufu = None

class Dotdict(dict):
    def __getattr__(self, name):
        return self[name]
    def __setattr__(self, name, value):
        self[name] = value
    def __delattr__(self, name):
        del self[name]
args = Dotdict({
    "NlLen": 512,           # Maximum length of natural language input
    "CodeLen": 512,         # Maximum length of code output
    "batch_size": 10,       # Batch size
    "batch_size_eval": 5,   # Batch size for beam search evaluation
    "embedding_size": 768,  # Dimension of embeddings
    "rulenum": 32216,       # Number of rules(types of tokens)
    "max_coqview_len": 160, # Maximum length of coqview
    "seed": 19970316,       # Random seed
    "lr":1e-4,              # Learning rate
    "coq_feature_lr": None, # Optional separate LR for a Qwen causal-DSL Coq feature branch
    "coq_feature_only": False, # Freeze ordinary parameters in the Qwen Coq representation ablation
    "max_epoch": 1000,      # Maximum number of epochs
    "epoch_offset": 0,      # Logical epoch offset for weight-only continuation runs
    "mask_id": 0,           # Mask/Pad token id
    "eval_step": 20,        # Evaluate model every eval_step
    "eval_step_init": 40,  # Evaluate model after eval_step_init
    "patience": 5,          # max number of epochs w/o improvement, reload model
    "max_num_trials": 3,    # max number of reloading before early stop
    "metric":"bleu",        # Model evaluation metric
    "precision": "bf16",    # Precision
    "task": "mbjp",         # Task name
    "eval": False,           # Evaluate model
    "train_time": "",
    "checkpoint_epoch": 200,
    "cut_prefix": False,     # Cut prefix from code output
    "empty_cuda_cache": 100, # Empty CUDA cache every empty_cuda_cache epochs
    "enable_coqview": False, # Enable coqview model
    "validation": True,      # Enable validation during training
    "evaluation_only": False, # Dataset has no train split and must not be fine-tuned
    "include_debug": False,    # Append optional debug.pkl rows to training
    "pretrain_name": "pretrain", # Pretrained model name
    "pretrain_model_type": "best", # Checkpoint type used only for the direct parent
    "no_swanlab": False,
    "limit_train_batches": 0,
    "output_tag": "",
    "model_output_task": "",
    "model_type": "best",
    "runtime_dir": "",
    "coq_candidate_multiplier": None,
    "coq_workers": 0,
    "coq_timeout": 20,
    "coq_final_only_check": False,
    "length_penalty": 0.1,
    "beam_size": 10,
    "early_stop_after_final_steps": None,
    "early_stop_max_first_final_len": None,
    "eval_split": "test",
    "eval_start": 0,
    "eval_limit": 0,
    "eval_indices": "",
    # 0 selects the task's observed target maximum (`max_code_len`).  Using
    # `CodeLen` here can include a long fixed prefix and lets constrained
    # decoding continue hundreds of tokens beyond every observed target.
    "eval_max_len": 0,
    "resume_output": False,
    "disable_tqdm": False,
    "force_coq_decoder": False,
    "force_sufu_type_check": False,
    "disable_sufu_grammar": False,
    "save_last_only": False,
    "cli_overrides": {},
    "coqview_max_step_offset": 0,
    "coqview_anchor_first_steps": 0,
    "coqview_random_window_steps": None,
    "coqview_prefix_replay_steps": 0,
    "coqview_prefix_replay_repeats": 0,
    "coqview_suffix_replay_steps": 0,
    "coqview_suffix_replay_repeats": 0,
    "coqview_extra_window_offsets": "",
    "coqview_extra_window_steps": 0,
    "coqview_extra_window_repeats": 0,
    "coqview_loss_reduction": "sum",
    "coqview_sync_last_only": False,
    "coqview_eval_mode_for_loss": False,
    "coqview_skip_backward_for_debug": False,
    "coqview_manual_distributed": True,
    "coqview_history_gradient_policy": "streaming_detached_self_kv",
    "train_only_expanded_embedding_rows": False,
    "base_vocab_rows": 0,
    "pad_train_shards_to_equal_batches": False,
    "train_num_workers": 10,
    "eval_num_workers": 2,
    "distributed_timeout_minutes": int(os.environ.get("PROOFT5_DISTRIBUTED_TIMEOUT_MINUTES", "60")),
    "ddp_find_unused_parameters": False,
})


def parse_int_list(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [int(item) for item in value]
    value = str(value).strip()
    if not value:
        return []
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def build_coqview_training_windows(config, global_rule_len, local_rule_len, epoch, batch_num):
    random_steps = global_rule_len
    if config.get("coqview_random_window_steps") is not None:
        random_steps = min(random_steps, int(config.coqview_random_window_steps))
    elif config.get("coqview_train_steps", 0):
        random_steps = min(random_steps, int(config.coqview_train_steps))

    anchor_steps = min(
        global_rule_len, int(config.get("coqview_anchor_first_steps", 0) or 0)
    )
    prefix_replay_steps = min(
        global_rule_len, int(config.get("coqview_prefix_replay_steps", 0) or 0)
    )
    prefix_replay_repeats = max(
        0, int(config.get("coqview_prefix_replay_repeats", 0) or 0)
    )
    suffix_replay_steps = min(
        global_rule_len, int(config.get("coqview_suffix_replay_steps", 0) or 0)
    )
    suffix_replay_repeats = max(
        0, int(config.get("coqview_suffix_replay_repeats", 0) or 0)
    )
    extra_window_steps = min(
        global_rule_len, int(config.get("coqview_extra_window_steps", 0) or 0)
    )
    extra_window_repeats = max(
        0, int(config.get("coqview_extra_window_repeats", 0) or 0)
    )
    extra_window_offsets = parse_int_list(config.get("coqview_extra_window_offsets", ""))

    max_step_offset = max(0, local_rule_len - random_steps)
    if config.get("coqview_max_step_offset", 0):
        max_step_offset = min(max_step_offset, int(config.coqview_max_step_offset))
    step_offset = 0
    if max_step_offset > anchor_steps:
        offset_span = max_step_offset - anchor_steps + 1
        step_offset = anchor_steps + (
            epoch * 1009 + batch_num * max(1, random_steps)
        ) % offset_span
    elif max_step_offset:
        step_offset = (
            epoch * 1009 + batch_num * max(1, random_steps)
        ) % (max_step_offset + 1)

    windows = []
    if anchor_steps:
        windows.append((anchor_steps, 0))
    windows.extend(
        (prefix_replay_steps, 0)
        for _ in range(prefix_replay_repeats)
        if prefix_replay_steps
    )
    if random_steps and not (
        anchor_steps and step_offset == 0 and random_steps <= anchor_steps
    ):
        windows.append((random_steps, step_offset))
    if extra_window_steps and extra_window_repeats and extra_window_offsets:
        max_extra_offset = max(0, global_rule_len - extra_window_steps)
        for _ in range(extra_window_repeats):
            for extra_offset in extra_window_offsets:
                windows.append(
                    (
                        extra_window_steps,
                        max(0, min(int(extra_offset), max_extra_offset)),
                    )
                )
    if suffix_replay_steps:
        suffix_offset = max(0, local_rule_len - suffix_replay_steps)
        windows.extend(
            (suffix_replay_steps, suffix_offset)
            for _ in range(suffix_replay_repeats)
        )
    return windows

class NoopSwanlab:
    def init(self, *args, **kwargs):
        return self
    def log(self, *args, **kwargs):
        return None
    def finish(self):
        return None

class MetricLogger:
    def __init__(self, logger, metrics_file="", tensorboard_dir=""):
        self.logger = logger
        self.metrics_file = metrics_file
        self.tensorboard_dir = tensorboard_dir
        self.fp = None
        self.writer = None
        self.step = 0
    def init(self, *args, **kwargs):
        self.logger.init(*args, **kwargs)
        if self.metrics_file:
            os.makedirs(os.path.dirname(self.metrics_file) or ".", exist_ok=True)
            self.fp = open(self.metrics_file, "a")
            atexit.register(self.finish)
        if self.tensorboard_dir:
            try:
                from torch.utils.tensorboard import SummaryWriter
                self.writer = SummaryWriter(self.tensorboard_dir)
                atexit.register(self.finish)
                config = kwargs.get("config")
                if config:
                    self.writer.add_text("config/json", json.dumps(config, indent=2), 0)
            except Exception as exc:
                print(f"TensorBoard disabled: {exc}")
                self.writer = None
        return self
    def log(self, metrics):
        self.logger.log(metrics)
        if self.fp is not None:
            record = {"time": datetime.now().isoformat(timespec="seconds"), **metrics}
            self.fp.write(json.dumps(record) + "\n")
            self.fp.flush()
        if self.writer is not None:
            for key, value in metrics.items():
                if isinstance(value, torch.Tensor):
                    value = value.detach().float().cpu().item()
                if isinstance(value, (int, float)):
                    self.writer.add_scalar(key, value, self.step)
                elif isinstance(value, str):
                    self.writer.add_text(key, value, self.step)
            self.writer.flush()
        self.step += 1
    def finish(self):
        self.logger.finish()
        if self.fp is not None and not self.fp.closed:
            self.fp.close()
        if self.writer is not None:
            self.writer.flush()
            self.writer.close()
            self.writer = None

class Communicate:
    def __init__(self, file_name="tmp/communicate.json"):
        self.filename = file_name
        os.makedirs(os.path.dirname(self.filename) or ".", exist_ok=True)
        if not os.path.exists(self.filename):
            with open(self.filename, "w") as f:
                json.dump({}, f)
    def set(self, name, value):
        with open(self.filename, "r") as f:
            info = json.load(f)
        info[name] = value
        with open(self.filename, "w") as f:
            json.dump(info, f)
    def get(self, name):
        with open(self.filename, "r") as f:
            info = json.load(f)
        return info[name]
commu = Communicate()

def save_model(model, dirs="Utils/models/Default/", model_type="best"):
    os.makedirs(dirs, exist_ok=True)
    target = os.path.join(dirs, f"{model_type}_model.ckpt")
    temporary = f"{target}.tmp-{os.getpid()}"
    try:
        torch.save(model.state_dict(), temporary)
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)


def snapshot_saved_model(source_dirs, source_type, target_dirs, target_type):
    source = os.path.join(source_dirs, f"{source_type}_model.ckpt")
    target = os.path.join(target_dirs, f"{target_type}_model.ckpt")
    os.makedirs(target_dirs, exist_ok=True)
    temporary = f"{target}.tmp-{os.getpid()}"
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)

def load_model(
    model,
    dirs="Utils/models/Default/",
    model_type="best",
    strict=False,
    allow_fallback=True,
):
    path = os.path.join(dirs, f"{model_type}_model.ckpt")
    if not os.path.exists(path):
        if not allow_fallback:
            raise FileNotFoundError(f"Requested model checkpoint not found: {path}")
        path = os.path.join(dirs, "last_model.ckpt")
    if not os.path.exists(path):
        print(f"Model not found in {dirs}")
        exit(1)
    state_dict = torch.load(path, map_location="cpu")
    try:
        model.load_state_dict(state_dict, strict=bool(strict))
    except RuntimeError:
        if strict:
            raise
        # Historical task tokenizers can contain a few task-local rows that
        # were added after the saved checkpoint. Preserve the checkpoint rows
        # and keep the model's initialized task-local rows in that case.
        current_state = model.state_dict()
        adapted = False
        for key in (
            "model.shared.weight",
            "model.encoder.embed_tokens.weight",
            "model.decoder.embed_tokens.weight",
            "lm_head.weight",
        ):
            saved = state_dict.get(key)
            current = current_state.get(key)
            if (
                saved is not None
                and current is not None
                and saved.ndim == current.ndim == 2
                and saved.shape[1:] == current.shape[1:]
                and saved.shape[0] != current.shape[0]
            ):
                merged = current.clone()
                rows = min(saved.shape[0], current.shape[0])
                merged[:rows].copy_(saved[:rows])
                state_dict[key] = merged
                adapted = True
        if not adapted:
            raise
        model.load_state_dict(state_dict, strict=False)
    return path


def configured_pretrain_model_type(config):
    checkpoint_type = str(config.get("pretrain_model_type", "best") or "best")
    if checkpoint_type not in {"best", "last", "final", "selected"} and not checkpoint_type.startswith("epoch"):
        raise ValueError(f"Unsupported pretrain_model_type: {checkpoint_type}")
    return checkpoint_type

def pad_tensor_dim(tensor, dim, target_size, value):
    current_size = tensor.size(dim)
    if current_size >= target_size:
        return tensor
    pad_shape = list(tensor.shape)
    pad_shape[dim] = target_size - current_size
    pad = torch.full(pad_shape, value, dtype=tensor.dtype, device=tensor.device)
    return torch.cat([tensor, pad], dim=dim)


def all_reduce_gradients(model, world_size, bucket_size_mb=128):
    if world_size <= 1:
        return
    bucket_limit = max(1, int(bucket_size_mb)) * 1024 * 1024
    bucket = []
    bucket_bytes = 0
    bucket_dtype = None
    bucket_device = None

    def flush_bucket():
        nonlocal bucket, bucket_bytes, bucket_dtype, bucket_device
        if not bucket:
            return
        flat = torch._utils._flatten_dense_tensors(bucket)
        torch.distributed.all_reduce(flat, op=torch.distributed.ReduceOp.SUM)
        flat.div_(world_size)
        for grad, reduced in zip(bucket, torch._utils._unflatten_dense_tensors(flat, bucket)):
            grad.copy_(reduced)
        bucket = []
        bucket_bytes = 0
        bucket_dtype = None
        bucket_device = None

    for parameter in model.parameters():
        if not parameter.requires_grad:
            continue
        if parameter.grad is None:
            parameter.grad = torch.zeros_like(parameter)
        grad = parameter.grad
        grad_bytes = grad.numel() * grad.element_size()
        if bucket and (
            grad.dtype != bucket_dtype
            or grad.device != bucket_device
            or bucket_bytes + grad_bytes > bucket_limit
        ):
            flush_bucket()
        if not bucket:
            bucket_dtype = grad.dtype
            bucket_device = grad.device
        bucket.append(grad)
        bucket_bytes += grad_bytes
    flush_bucket()

def set_process_group_timeout(accelerator, timeout_minutes, label):
    if not (torch.distributed.is_available() and torch.distributed.is_initialized()):
        return
    timeout = timedelta(minutes=int(timeout_minutes))
    try:
        from torch.distributed import distributed_c10d

        groups = list(distributed_c10d._world.pg_map.keys())
        for group in groups:
            distributed_c10d._set_pg_timeout(timeout, group=group)
        if accelerator.is_main_process:
            print(f"Set distributed process-group timeout to {timeout} after {label} for {len(groups)} group(s)")
    except Exception as exc:
        if accelerator.is_main_process:
            print(f"Warning: could not set distributed process-group timeout after {label}: {exc}")

def load_rules_for_task(task):
    rules = pickle.load(open(f"Utils/data/{task}/rules.pkl", "rb"))
    task_config = json.load(open(f"Utils/data/{task}/config.json", "r"))
    config_rulenum = task_config.get("rulenum")
    if config_rulenum and config_rulenum < len(rules):
        rules = {rule: idx for rule, idx in rules.items() if idx < config_rulenum}
    return rules

def load_tokenizer_for_task(task):
    for name in ["coq_tokenizer.pkl", "tokenizer.pkl"]:
        path = f"Utils/data/{task}/{name}"
        if os.path.exists(path):
            return pickle.load(open(path, "rb"))
    return None

def output_candidate_complete(path):
    if not os.path.exists(path):
        return False
    try:
        with open(path, "r") as f:
            first_line = f.readline()
    except OSError:
        return False
    return bool(first_line) and not first_line.startswith("IndexError:")

def build_model_for_task():
    if args.get("model_family") == "qwen_causal_dsl":
        if MyQwenCausalDsl is None:
            raise RuntimeError("Qwen causal DSL support requires transformers and torch.")
        return MyQwenCausalDsl(args)
    if args.get("model_family") == "codegemma_causal_dsl":
        if MyCodeGemmaCausalDsl is None:
            raise RuntimeError(
                "CodeGemma causal DSL support requires transformers and torch."
            )
        return MyCodeGemmaCausalDsl(args)
    if args.get("model_family") == "t5gemma2":
        if MyT5Gemma2 is None:
            raise RuntimeError("T5Gemma2 support requires transformers 5.x; use the prooft5-t5gemma uv env.")
        return MyT5Gemma2withCoq1(args) if args.enable_coqview else MyT5Gemma2(args)
    return MyT5withCoq1(args) if args.enable_coqview else MyT5(args)


def configure_expanded_embedding_only_training(model, base_vocab_rows):
    """Freeze the backbone and update only vocabulary rows added after the base LM."""
    base_vocab_rows = int(base_vocab_rows)
    if base_vocab_rows <= 0:
        raise ValueError("base_vocab_rows must be positive for embedding-only training")
    embedding = model.seq2seq.model.encoder.text_model.embed_tokens.weight
    if base_vocab_rows >= embedding.shape[0]:
        raise ValueError(
            f"base_vocab_rows={base_vocab_rows} must be smaller than "
            f"expanded vocabulary size {embedding.shape[0]}"
        )
    tied_parameters = (
        embedding,
        model.seq2seq.model.decoder.embed_tokens.weight,
        model.seq2seq.lm_head.out_proj.weight,
    )
    if len({parameter.data_ptr() for parameter in tied_parameters}) != 1:
        raise RuntimeError("encoder, decoder, and output embeddings are not tied")
    for parameter in model.parameters():
        parameter.requires_grad_(False)
    embedding.requires_grad_(True)

    def zero_base_rows(gradient):
        gradient[:base_vocab_rows].zero_()
        return gradient

    embedding.register_hook(zero_base_rows)
    return embedding.shape[0] - base_vocab_rows


def aggregate_distributed_token_mean(rank_losses, rank_active_target_tokens):
    """Combine per-rank token-mean losses without counting padding tokens."""
    rank_losses = [float(value) for value in rank_losses]
    rank_active_target_tokens = [int(value) for value in rank_active_target_tokens]
    if len(rank_losses) != len(rank_active_target_tokens) or not rank_losses:
        raise ValueError("rank losses and target-token counts must have equal nonzero length")
    if any(not np.isfinite(value) for value in rank_losses):
        raise ValueError("rank losses must be finite")
    if any(value < 0 for value in rank_active_target_tokens):
        raise ValueError("rank target-token counts must be non-negative")
    total_tokens = sum(rank_active_target_tokens)
    if total_tokens <= 0:
        raise ValueError("distributed batch contains no active target tokens")
    return (
        sum(
            rank_loss * rank_tokens
            for rank_loss, rank_tokens in zip(
                rank_losses, rank_active_target_tokens
            )
        )
        / total_tokens
    )


def count_active_target_tokens(input_res, mask_id, has_prefix=False):
    """Count targets used by MyT5/MyT5Gemma2 cross entropy."""
    targets = input_res if has_prefix else input_res[:, 1:]
    return int(torch.ne(targets, mask_id).sum().item())


def distributed_token_mean_backward_scale(
    local_active_target_tokens, global_active_target_tokens, process_count
):
    """Scale a local token mean so DDP's rank mean becomes a global token mean."""
    local_active_target_tokens = int(local_active_target_tokens)
    global_active_target_tokens = int(global_active_target_tokens)
    process_count = int(process_count)
    if local_active_target_tokens < 0 or global_active_target_tokens <= 0:
        raise ValueError("active target-token counts are invalid")
    if process_count <= 0:
        raise ValueError("process count must be positive")
    if local_active_target_tokens > global_active_target_tokens:
        raise ValueError("local target-token count exceeds the global count")
    return process_count * local_active_target_tokens / global_active_target_tokens


def load_beam_searches():
    global BeamSearch, BeamSearchCoq, BeamSearchDsl, BeamSearchSufu
    if BeamSearch is None:
        from beamsearch import BeamSearch as _BeamSearch
        from beamsearch_coq import BeamSearch as _BeamSearchCoq
        from beamsearch_dsl import BeamSearch as _BeamSearchDsl
        from beamsearch_sufu import BeamSearch as _BeamSearchSufu
        BeamSearch = _BeamSearch
        BeamSearchCoq = _BeamSearchCoq
        BeamSearchDsl = _BeamSearchDsl
        BeamSearchSufu = _BeamSearchSufu

def partition_data_rows(data, process_num, add_zero_loss_padding=False):
    if len(data) % process_num != 0:
        datalen = len(data) // process_num + 1
    else:
        datalen = len(data) // process_num
    original_lengths = [datalen] * process_num
    for i in range(datalen * process_num - len(data)):
        original_lengths[i] -= 1

    shards = []
    split_point = 0
    for i in range(process_num):
        shard = list(data[split_point : split_point + original_lengths[i]])
        split_point += original_lengths[i]
        shards.append(shard)

    padding_counts = [0] * process_num
    if add_zero_loss_padding and shards:
        target_len = max(len(shard) for shard in shards)
        for i, shard in enumerate(shards):
            if not shard and target_len:
                raise ValueError("Cannot pad an empty distributed train shard")
            while len(shard) < target_len:
                padding_row = dict(shard[-1])
                padding_row["_distributed_zero_loss_padding"] = True
                shard.append(padding_row)
                padding_counts[i] += 1
    return shards, original_lengths, padding_counts


def partition_selected_eval_rows(data, process_num, eval_indices):
    """Select global eval rows first, then distribute them evenly across ranks."""
    requested = [int(index) for index in eval_indices]
    if len(requested) != len(set(requested)):
        raise ValueError("eval_indices contains duplicates")
    invalid = [index for index in requested if index < 0 or index >= len(data)]
    if invalid:
        raise ValueError(f"eval_indices out of range: {invalid}")
    problem_ids = sorted(requested)
    selected_rows = [data[index] for index in problem_ids]
    row_shards, original_lengths, padding_counts = partition_data_rows(
        selected_rows, process_num, add_zero_loss_padding=False
    )
    id_shards, id_lengths, _ = partition_data_rows(
        problem_ids, process_num, add_zero_loss_padding=False
    )
    if original_lengths != id_lengths:
        raise AssertionError("selected eval row/id partition mismatch")
    return row_shards, id_shards, original_lengths, padding_counts


def distributed_eval_range_slice(
    shard_start,
    shard_length,
    global_length,
    eval_start=0,
    eval_limit=0,
):
    shard_start = int(shard_start)
    shard_length = int(shard_length)
    global_length = int(global_length)
    range_start = min(max(0, int(eval_start or 0)), global_length)
    range_end = global_length
    if int(eval_limit or 0) > 0:
        range_end = min(global_length, range_start + int(eval_limit))
    shard_end = shard_start + shard_length
    overlap_start = max(shard_start, range_start)
    overlap_end = min(shard_end, range_end)
    if overlap_end <= overlap_start:
        return 0, 0, overlap_start
    return (
        overlap_start - shard_start,
        overlap_end - shard_start,
        overlap_start,
    )


def distributed_eval_index_positions(
    shard_start,
    shard_length,
    global_length,
    eval_indices,
):
    """Return (local position, global id) pairs for arbitrary eval rows."""
    shard_start = int(shard_start)
    shard_length = int(shard_length)
    global_length = int(global_length)
    requested = [int(index) for index in eval_indices]
    if len(requested) != len(set(requested)):
        raise ValueError("eval_indices contains duplicates")
    invalid = [index for index in requested if index < 0 or index >= global_length]
    if invalid:
        raise ValueError(f"eval_indices out of range: {invalid}")
    requested = sorted(requested)
    shard_end = shard_start + shard_length
    return [
        (index - shard_start, index)
        for index in requested
        if shard_start <= index < shard_end
    ]


def resolve_eval_decode_max_len(config):
    """Use the observed target maximum unless the caller asks for another cap."""
    requested = int(config.get("eval_max_len", 0) or 0)
    if requested > 0:
        return requested
    observed_target_max = int(config.get("max_code_len", 0) or 0)
    if observed_target_max > 0:
        return observed_target_max
    if hasattr(config, "CodeLen"):
        return int(config.CodeLen)
    return int(config["CodeLen"])


def resolve_sufu_decoder_options(config):
    """Resolve SuFu decoder features from model config, not task spelling."""
    enable_coqview = bool(config.get("enable_coqview", False))
    task = str(config.get("task", ""))
    legacy_coqview_name = "sufucoqview" in task
    return {
        "type_check": bool(
            config.get("force_sufu_type_check", False)
            or enable_coqview
            or legacy_coqview_name
            or ("sufucoq" in task and not legacy_coqview_name)
        ),
        "add_type_ctx": enable_coqview or legacy_coqview_name,
    }


def split_data(process_num, tasktype):
    data = pickle.load(open(f"Utils/data/{args.task}/{tasktype}.pkl", "rb"))
    if tasktype == "train" and args.get("include_debug", False):
        debug_path = f"Utils/data/{args.task}/debug.pkl"
        if not os.path.exists(debug_path):
            raise FileNotFoundError(
                f"--include_debug requested, but {debug_path} does not exist"
            )
        debug_rows = pickle.load(open(debug_path, "rb"))
        if any(not row.get("debug_overlap", False) for row in debug_rows):
            raise RuntimeError(f"Unmarked row found in debug split {debug_path}")
        data.extend(debug_rows)
        print(
            "Included "
            f"{len(debug_rows)} additional rows in the complete training set."
        )
    add_zero_loss_padding = bool(
        tasktype == "train"
        and not args.eval
        and args.get("pad_train_shards_to_equal_batches", False)
    )
    requested_indices = parse_int_list(args.get("eval_indices", ""))
    selected_problem_ids = None
    if args.eval and requested_indices and tasktype == args.get("eval_split", "test"):
        shards, selected_problem_ids, original_lengths, padding_counts = (
            partition_selected_eval_rows(data, process_num, requested_indices)
        )
    else:
        shards, original_lengths, padding_counts = partition_data_rows(
            data,
            process_num,
            add_zero_loss_padding=add_zero_loss_padding,
        )
    actual_lengths = [len(shard) for shard in shards]
    for i, shard in enumerate(shards):
        shard_path = os.path.join(args.runtime_dir, f"data_{tasktype}{i}.pkl")
        with open(shard_path, "wb") as f:
            pickle.dump(shard, f)
    commu.set(f"{tasktype}_data_len", actual_lengths)
    commu.set(f"{tasktype}_original_data_len", original_lengths)
    commu.set(f"{tasktype}_zero_loss_padding", padding_counts)
    if selected_problem_ids is not None:
        commu.set(f"{tasktype}_problem_ids", selected_problem_ids)
    print(f"{tasktype}_set length : {commu.get(f"{tasktype}_data_len")}, total length : {len(data)}")
    if any(padding_counts):
        print(
            f"{tasktype}_set zero-loss distributed padding: {padding_counts}; "
            f"original shard lengths: {original_lengths}"
        )

def finetune():
    global args, commu
    date = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    taskconfig = json.loads(open("Utils/data/%s/config.json" % args.task, "r").read())
    for key in taskconfig:
        setattr(args, key, taskconfig[key])
        if key == "max_code_len":
            args.CodeLen = taskconfig[key]
    for key, value in args.get("cli_overrides", {}).items():
        setattr(args, key, value)
    if args.get("evaluation_only", False) and not args.eval:
        raise RuntimeError(
            f"Task {args.task!r} is evaluation-only and cannot be used for fine-tuning."
        )
    model_output_task = args.get("model_output_task", "") or (
        f"{args.task}_debug"
        if args.get("include_debug", False)
        else args.task
    )
    runtime_key = "".join(
        ch if ch.isalnum() or ch in "._-" else "_" for ch in model_output_task
    )
    args.runtime_dir = args.get("runtime_dir", "") or os.path.join(
        "tmp", "runtime_state", runtime_key
    )
    os.makedirs(args.runtime_dir, exist_ok=True)
    commu = Communicate(os.path.join(args.runtime_dir, "communicate.json"))
    is_pretrain_task = args.task.startswith("pretrain")

    # Initialize accelerator & split train, dev, test data
    accelerator_handlers = [
        InitProcessGroupKwargs(timeout=timedelta(minutes=int(args.distributed_timeout_minutes)))
    ]
    if args.get("ddp_find_unused_parameters", False):
        accelerator_handlers.append(
            DistributedDataParallelKwargs(find_unused_parameters=True)
        )
    accelerator = Accelerator(
        mixed_precision=args.precision,
        kwargs_handlers=accelerator_handlers,
    )
    set_process_group_timeout(accelerator, args.distributed_timeout_minutes, "accelerator init")
    if accelerator.is_main_process:
        split_data(accelerator.num_processes, "train")
        if not is_pretrain_task:
            if args.validation:
                split_data(accelerator.num_processes, "valid")
            split_data(accelerator.num_processes, "test")
    accelerator.wait_for_everyone()

    # configuration
    pindex = accelerator.process_index
    torch.manual_seed(args.seed + accelerator.process_index)
    np.random.seed(args.seed + accelerator.process_index)
    random.seed(args.seed + accelerator.process_index)
    device = accelerator.device

    # load word table & model
    newruledic = load_rules_for_task(args.task)
    runtime_rulenum = len(newruledic)
    model_init_rulenum = runtime_rulenum
    if not args.get("init_from_hf", False):
        try:
            model_init_rulenum = len(load_rules_for_task(args.pretrain_name))
        except Exception:
            model_init_rulenum = runtime_rulenum
    args.rulenum = model_init_rulenum
    model = build_model_for_task()
    if not args.get("init_from_hf", False):
        strict_model_loading = bool(args.get("strict_model_loading", False))
        load_model(
            model,
            "Utils/models/Model%s/" % args.pretrain_name,
            model_type=configured_pretrain_model_type(args),
            strict=strict_model_loading,
            allow_fallback=not strict_model_loading,
        )
    args.rulenum = runtime_rulenum
    model.resize_token_embeddings(args.rulenum)
    if args.get("train_only_expanded_embedding_rows", False):
        expanded_rows = configure_expanded_embedding_only_training(
            model, args.get("base_vocab_rows", 0)
        )
        if accelerator.is_main_process:
            print(
                "Embedding-only adaptation enabled: "
                f"training {expanded_rows} expanded rows and freezing the backbone"
            )
    
    # load dataset & print configuration
    train_set = SumDataset(args, "train", idx=accelerator.process_index)
    if not is_pretrain_task:
        dev_set = SumDataset(args, "valid" if args.validation else "test", idx=accelerator.process_index)
        test_set = SumDataset(args, "test", idx=accelerator.process_index)
    if accelerator.is_main_process:
        print("Model loaded")
        print("config is :", end = " ")
        beeprint.pp(args)

    #prepare optimizer
    if accelerator.state.deepspeed_plugin is not None:
        accelerator.state.deepspeed_plugin.deepspeed_config[
            "train_micro_batch_size_per_gpu"
        ] = args.batch_size
    coq_feature_lr = args.get("coq_feature_lr")
    coq_feature_only = bool(
        args.get("model_family") in {"qwen_causal_dsl", "codegemma_causal_dsl"}
        and args.enable_coqview
        and args.get("coq_feature_only", False)
    )
    if coq_feature_only:
        feature_parameter_ids = {
            id(model.coq_gate),
            *(id(parameter) for parameter in model.coq_projection.parameters()),
        }
        for parameter in model.parameters():
            parameter.requires_grad_(id(parameter) in feature_parameter_ids)
        if accelerator.is_main_process:
            print(
                "Qwen causal-DSL representation-only continuation enabled: "
                "ordinary backbone/DSL parameters frozen"
            )
    if (
        args.get("model_family") in {"qwen_causal_dsl", "codegemma_causal_dsl"}
        and args.enable_coqview
        and coq_feature_lr is not None
    ):
        feature_parameters = [model.coq_gate, *model.coq_projection.parameters()]
        feature_parameter_ids = {id(parameter) for parameter in feature_parameters}
        backbone_parameters = [
            parameter
            for parameter in model.parameters()
            if parameter.requires_grad and id(parameter) not in feature_parameter_ids
        ]
        parameter_groups = []
        if backbone_parameters:
            parameter_groups.append({"params": backbone_parameters, "lr": args.lr})
        parameter_groups.append(
            {"params": feature_parameters, "lr": float(coq_feature_lr)}
        )
        optimizer = optim.AdamW(parameter_groups, eps=1e-8)
        if accelerator.is_main_process:
            if backbone_parameters:
                print(
                    "Qwen causal-DSL Coq feature learning rate enabled: "
                    f"backbone={args.lr:g}, feature={float(coq_feature_lr):g}"
                )
            else:
                print(
                    "Qwen causal-DSL Coq feature-only optimizer enabled: "
                    f"feature={float(coq_feature_lr):g}"
                )
    else:
        optimizer = optim.AdamW(model.parameters(), eps=1e-8, lr=args.lr)
    manual_coqview_distributed = bool(
        args.get("coqview_manual_distributed", True)
        and args.enable_coqview
        and args.get("model_family") == "t5gemma2"
        and args.cut_prefix
        and accelerator.num_processes > 1
    )
    if manual_coqview_distributed:
        if accelerator.state.deepspeed_plugin is not None:
            raise RuntimeError(
                "T5Gemma2 CoqView manual distributed training requires a DDP "
                "Accelerate config without DeepSpeed."
            )
        model = model.to(device)
    else:
        model, optimizer = accelerator.prepare(model, optimizer)
    accelerator.register_for_checkpointing(model)
    accelerator.register_for_checkpointing(optimizer)
    set_process_group_timeout(accelerator, args.distributed_timeout_minutes, "accelerator prepare")

    # Evaluate model
    if args.eval:
        eval_model = model.module if hasattr(model, "module") else model
        strict_model_loading = bool(args.get("strict_model_loading", False))
        if args.train_time:
            load_model(
                eval_model,
                f"Utils/models/Model{model_output_task}/{args.train_time}/",
                model_type=f"epoch{args.checkpoint_epoch}",
                strict=strict_model_loading,
                allow_fallback=not strict_model_loading,
            )
        else:
            load_model(
                eval_model,
                f"Utils/models/Model{model_output_task}/",
                model_type=args.model_type,
                strict=strict_model_loading,
                allow_fallback=not strict_model_loading,
            )
        eval_sets = {"train": train_set, "valid": dev_set, "test": test_set}
        testmodel(eval_sets[args.eval_split], model, device, accelerator, newruledic)
        exit(0)

    # Fine-tune model
    if accelerator.is_main_process:
        base_logger = NoopSwanlab() if args.no_swanlab or swanlab is None else swanlab
        tensorboard_dir = args.get("tensorboard_dir", "") or f"Utils/tensorboard/{args.task}/{date}"
        metrics_file = args.get("metrics_file", "")
    else:
        base_logger = NoopSwanlab()
        tensorboard_dir = ""
        metrics_file = ""
    logger = MetricLogger(base_logger, metrics_file, tensorboard_dir)
    logger.init(
        project=args.task,
        experiment_name=f"{args.task}_{date}",
        config={
            "learning_rate": args.lr, 
        },
    )
    if accelerator.is_main_process:
        logger.log(
            {
                "event": "training_configuration",
                "base_seed": int(args.seed),
                "rank_seeds": [
                    int(args.seed) + rank
                    for rank in range(accelerator.num_processes)
                ],
                "world_size": int(accelerator.num_processes),
            }
        )
    num_trial = patience = 0
    maxBleu = 0
    epoch_offset = int(args.get("epoch_offset", 0) or 0)
    for local_epoch in trange(args.max_epoch+1, desc=f"Processer {pindex}"):
        epoch = epoch_offset + local_epoch
        # eval model using dev set, early stop if no improvement
        if epoch % args.eval_step == 0 and epoch >= args.eval_step_init:
            if args.validation:
                tnum, bleu = evalmodel(dev_set, model, device, accelerator, newruledic)
                if accelerator.is_main_process:
                    unwrapped_model = accelerator.unwrap_model(model)
                    root_model_dir = f"Utils/models/Model{model_output_task}/"
                    epoch_model_dir = f"Utils/models/Model{model_output_task}/{date}/"
                    save_model(unwrapped_model, root_model_dir, model_type="last")
                    if not args.save_last_only:
                        snapshot_saved_model(
                            root_model_dir,
                            "last",
                            epoch_model_dir,
                            f"epoch{epoch}",
                        )
                    commu.set("reload", False)
                    commu.set("exit", False)
                    
                    if maxBleu < bleu:
                        maxBleu = bleu
                        patience = 0
                        snapshot_saved_model(root_model_dir, "last", root_model_dir, "best")
                        if not args.save_last_only:
                            snapshot_saved_model(
                                root_model_dir,
                                "best",
                                epoch_model_dir,
                                "best",
                            )
                    else:
                        patience += 1
                        if patience >= args.patience:  # patience exhausted, reload
                            num_trial += 1
                            if num_trial >= args.max_num_trials:
                                print("Early stop!")
                                commu.set("exit", True)
                            commu.set("reload", True)
                            print("Reload model")
                            patience = 0
                    print(f"dev_bleu: {bleu}, patience: {patience}, trial: {num_trial}")
                    logger.log({
                            "dev_bleu": bleu,
                            "patience": patience,
                            "trial": num_trial,
                    })
                accelerator.wait_for_everyone()
                if commu.get("exit"):
                    exit(0)
                if commu.get("reload"):
                    load_model(
                        model.module if hasattr(model, "module") else model,
                        f"Utils/models/Model{model_output_task}/",
                    )
                    for param_group in optimizer.param_groups:
                        param_group["lr"] = 0.5 * param_group["lr"]
                accelerator.wait_for_everyone()
            else:
                if accelerator.is_main_process:
                    unwrapped_model = accelerator.unwrap_model(model)
                    root_model_dir = f"Utils/models/Model{model_output_task}/"
                    epoch_model_dir = f"Utils/models/Model{model_output_task}/{date}/"
                    save_model(unwrapped_model, root_model_dir, model_type="last")
                    if not args.save_last_only:
                        snapshot_saved_model(
                            root_model_dir,
                            "last",
                            epoch_model_dir,
                            f"epoch{epoch}",
                        )
                accelerator.wait_for_everyone()
        
        tot_runtime = 0
        sampler = ChunkedRandomSampler(train_set, args.batch_size)
        data_loader = torch.utils.data.DataLoader(
            dataset=train_set,
            batch_size=args.batch_size,
            drop_last=False,
            num_workers=args.train_num_workers,
            collate_fn=rs_collate_fn_cutprefix if args.cut_prefix else rs_collate_fn,
            sampler=sampler,
            pin_memory=True,
        )

        batch_num=0
        model.train()
        if args.enable_coqview and args.get("coqview_eval_mode_for_loss", False):
            model.eval()
        for dBatch in data_loader:
            for x in dBatch:
                dBatch[x] = dBatch[x].to(device)
            local_padding_rows = int(
                dBatch.get(
                    "distributed_zero_loss_padding",
                    torch.zeros(1, device=device, dtype=torch.bool),
                ).sum().item()
            )
            gathered_padding_rows = accelerator.gather(
                torch.tensor([local_padding_rows], device=device, dtype=torch.long)
            )
            starttime = time.time()
            backward_done = False
            if (
                args.enable_coqview
                and args.get("model_family") == "t5gemma2"
                and args.cut_prefix
                and hasattr(model.module if hasattr(model, "module") else model, "coqview_step_losses")
            ):
                step_model = model.module if hasattr(model, "module") else model
                step_losses = []
                local_rule_len = int(torch.ne(dBatch["res"], args.mask_id).sum(dim=1).max().item())
                local_steps = torch.tensor([local_rule_len], device=device, dtype=torch.long)
                global_rule_len = int(accelerator.gather(local_steps).max().item())
                dBatch["res"] = pad_tensor_dim(dBatch["res"], 1, global_rule_len, args.mask_id)
                dBatch["coqview"] = pad_tensor_dim(dBatch["coqview"], 1, global_rule_len, args.mask_id)
                coqview_windows = build_coqview_training_windows(
                    args,
                    global_rule_len=global_rule_len,
                    local_rule_len=local_rule_len,
                    epoch=epoch,
                    batch_num=batch_num,
                )

                loss_reduction = str(args.get("coqview_loss_reduction", "sum")).lower()
                if loss_reduction not in {"sum", "mean"}:
                    raise ValueError(f"Unsupported coqview_loss_reduction: {loss_reduction}")
                scheduled_steps = sum(total_steps for total_steps, _ in coqview_windows)
                local_active_targets = 0
                for total_steps, window_offset in coqview_windows:
                    window_end = min(dBatch["res"].size(1), window_offset + total_steps)
                    local_active_targets += int(
                        torch.ne(
                            dBatch["res"][:, window_offset:window_end],
                            args.mask_id,
                        ).sum().item()
                    )
                active_tensor = torch.tensor([local_active_targets], device=device, dtype=torch.long)
                gathered_active_targets = accelerator.gather(active_tensor)
                global_active_targets = int(gathered_active_targets.sum().item())
                loss_scale = (
                    accelerator.num_processes / max(1, global_active_targets)
                    if loss_reduction == "mean"
                    else 1.0
                )
                sync_last_only = bool(args.get("coqview_sync_last_only", False))
                sync_last_only = (
                    sync_last_only
                    and not manual_coqview_distributed
                    and accelerator.num_processes > 1
                    and accelerator.state.deepspeed_plugin is None
                    and hasattr(model, "no_sync")
                )
                backward_index = 0
                raw_step_losses = []

                def train_coqview_window(total_steps, window_offset):
                    nonlocal backward_index
                    loss_iter = iter(step_model.coqview_step_losses(
                        dBatch["nl"],
                        dBatch["res"],
                        dBatch["coqview"],
                        dBatch["prefix"],
                        total_steps=total_steps,
                        step_offset=window_offset,
                        loss_reduction="sum" if loss_reduction == "mean" else "mean",
                        history_gradient_policy=args.get(
                            "coqview_history_gradient_policy",
                            "streaming_detached_self_kv",
                        ),
                    ))
                    for _ in range(total_steps):
                        is_last_backward = backward_index + 1 == scheduled_steps
                        sync_context = (
                            accelerator.no_sync(model)
                            if sync_last_only and not is_last_backward
                            else nullcontext()
                        )
                        # DDP requires both the forward and backward pass to be
                        # inside no_sync(), so advance the generator here.
                        with sync_context:
                            with accelerator.autocast():
                                raw_step_loss = next(loss_iter)
                            step_loss = raw_step_loss * loss_scale
                            if not args.get("coqview_skip_backward_for_debug", False):
                                accelerator.backward(step_loss)
                        step_losses.append(step_loss.detach())
                        raw_step_losses.append(raw_step_loss.detach().float().clone())
                        backward_index += 1

                for total_steps, window_offset in coqview_windows:
                    train_coqview_window(total_steps, window_offset)
                if loss_reduction == "mean" and raw_step_losses:
                    local_loss_sum = torch.stack(raw_step_losses).sum().reshape(1)
                    gathered_loss_sums = accelerator.gather(local_loss_sum)
                    loss = gathered_loss_sums.sum() / max(1, global_active_targets)
                else:
                    gathered_loss_sums = None
                    loss = torch.stack(step_losses).sum() if step_losses else torch.tensor(0.0, device=device)
                info = {
                    "coqview_scheduled_steps": scheduled_steps,
                    "coqview_local_rule_len": local_rule_len,
                    "coqview_global_rule_len": global_rule_len,
                    "coqview_active_targets": local_active_targets,
                    "coqview_global_active_targets": global_active_targets,
                    "coqview_rank_active_targets": [
                        int(value) for value in gathered_active_targets.cpu().tolist()
                    ],
                    "coqview_rank_loss_sums": (
                        [float(value) for value in gathered_loss_sums.cpu().tolist()]
                        if gathered_loss_sums is not None
                        else []
                    ),
                    "coqview_loss_scale": loss_scale,
                    "coqview_sync_last_only": int(sync_last_only),
                    "coqview_eval_mode_for_loss": int(not step_model.training),
                    "coqview_skip_backward_for_debug": int(
                        bool(args.get("coqview_skip_backward_for_debug", False))
                    ),
                    "coqview_manual_distributed": int(manual_coqview_distributed),
                    "coqview_history_gradient_policy": args.get(
                        "coqview_history_gradient_policy",
                        "streaming_detached_self_kv",
                    ),
                }
                backward_done = True
            elif args.enable_coqview:
                forward_res = dBatch["res"]
                qwen_padding_only = bool(
                    args.get("model_family") in {"qwen_causal_dsl", "codegemma_causal_dsl"}
                    and local_padding_rows == int(dBatch["res"].size(0))
                    and "distributed_zero_loss_padding_res" in dBatch
                )
                if qwen_padding_only:
                    forward_res = dBatch["distributed_zero_loss_padding_res"]
                loss, info = model(dBatch["nl"], forward_res, dBatch["coqview"],
                                   inputprefix=dBatch["prefix"] if args.cut_prefix else None)
                if args.get("model_family") in {"qwen_causal_dsl", "codegemma_causal_dsl"}:
                    if qwen_padding_only:
                        loss = loss * 0.0
                    local_active_target_tokens = int(
                        0 if qwen_padding_only else info.get(
                            "active_targets",
                            count_active_target_tokens(
                                dBatch["res"], args.mask_id, has_prefix=bool(args.cut_prefix)
                            ),
                        )
                    )
                    gathered_active_target_tokens = accelerator.gather(
                        torch.tensor(
                            [local_active_target_tokens], device=device, dtype=torch.long
                        )
                    )
                    gathered_rank_losses = accelerator.gather(
                        loss.detach().float().reshape(1)
                    )
                    rank_active_target_tokens = [
                        int(value) for value in gathered_active_target_tokens.cpu().tolist()
                    ]
                    rank_losses = [
                        float(value) for value in gathered_rank_losses.cpu().tolist()
                    ]
                    global_active_target_tokens = sum(rank_active_target_tokens)
                    global_token_weighted_loss = aggregate_distributed_token_mean(
                        rank_losses, rank_active_target_tokens
                    )
                    distributed_loss_scale = distributed_token_mean_backward_scale(
                        local_active_target_tokens,
                        global_active_target_tokens,
                        accelerator.num_processes,
                    )
                    info.update(
                        {
                            "local_rank_loss": float(loss.detach().item()),
                            "global_token_weighted_loss": global_token_weighted_loss,
                            "global_active_target_tokens": global_active_target_tokens,
                            "rank_active_target_tokens": rank_active_target_tokens,
                            "rank_losses": rank_losses,
                            "distributed_token_mean_backward_scale": distributed_loss_scale,
                        }
                    )
                    loss = loss * distributed_loss_scale
            else:
                forward_res = dBatch["res"]
                if (
                    local_padding_rows == int(dBatch["res"].size(0))
                    and "distributed_zero_loss_padding_res" in dBatch
                ):
                    forward_res = dBatch["distributed_zero_loss_padding_res"]
                loss, info = model(
                    dBatch["nl"],
                    forward_res,
                    inputprefix=dBatch["prefix"] if args.cut_prefix and "prefix" in dBatch else None,
                )
                if local_padding_rows == int(dBatch["res"].size(0)):
                    loss = loss * 0.0
                # ``loss`` is a token mean computed independently on every
                # distributed rank.  Logging only rank 0's scalar makes
                # checkpoint selection depend on one data shard.  Reconstruct
                # the global, non-padding token mean for metrics while keeping
                # the original local loss for DDP backward semantics.
                local_active_target_tokens = count_active_target_tokens(
                    dBatch["res"],
                    args.mask_id,
                    has_prefix=bool(args.cut_prefix and "prefix" in dBatch),
                )
                gathered_active_target_tokens = accelerator.gather(
                    torch.tensor(
                        [local_active_target_tokens], device=device, dtype=torch.long
                    )
                )
                gathered_rank_losses = accelerator.gather(
                    loss.detach().float().reshape(1)
                )
                global_active_target_tokens = int(
                    gathered_active_target_tokens.sum().item()
                )
                rank_losses = [
                    float(value) for value in gathered_rank_losses.cpu().tolist()
                ]
                rank_active_target_tokens = [
                    int(value)
                    for value in gathered_active_target_tokens.cpu().tolist()
                ]
                global_token_weighted_loss = aggregate_distributed_token_mean(
                    rank_losses, rank_active_target_tokens
                )
                distributed_loss_scale = distributed_token_mean_backward_scale(
                    local_active_target_tokens,
                    global_active_target_tokens,
                    accelerator.num_processes,
                )
                info.update(
                    {
                        "local_rank_loss": float(loss.detach().item()),
                        "global_token_weighted_loss": global_token_weighted_loss,
                        "global_active_target_tokens": global_active_target_tokens,
                        "rank_active_target_tokens": rank_active_target_tokens,
                        "rank_losses": rank_losses,
                        "distributed_token_mean_backward_scale": distributed_loss_scale,
                    }
                )
                loss = loss * distributed_loss_scale
            info["distributed_zero_loss_padding_rows"] = local_padding_rows
            info["global_distributed_zero_loss_padding_rows"] = int(
                gathered_padding_rows.sum().item()
            )
            info["rank_distributed_zero_loss_padding_rows"] = [
                int(value) for value in gathered_padding_rows.cpu().tolist()
            ]
            tot_runtime += time.time() - starttime

            if not torch.isfinite(loss.detach()).item():
                with open("tmp/log.txt", "w") as f:
                    f.write(
                        f"non-finite loss {loss.item()} at process {pindex}, "
                        f"epoch {epoch}, batch {batch_num}\n"
                    )
                    f.write(f"nl: {dBatch['nl']}\n")
                with open("tmp/dbatch.pkl", "wb") as f:
                    pickle.dump(dBatch, f)
                save_model(
                    model.module if hasattr(model, "module") else model,
                    f"Utils/models/Model{model_output_task}/",
                    model_type="last",
                )
                assert 0
            batch_num += 1
            if not backward_done:
                accelerator.backward(loss)
            if (
                manual_coqview_distributed
                and backward_done
                and not args.get("coqview_skip_backward_for_debug", False)
            ):
                all_reduce_gradients(model, accelerator.num_processes)
            optimizer.step()  
            optimizer.zero_grad()
            lr = optimizer.param_groups[0]["lr"]
            metric_loss = float(
                info.get("global_token_weighted_loss", loss.detach().item())
            )
            batch_metrics = {
                "loss": metric_loss,
                "lr": lr,
                "epoch": epoch,
                "batch": batch_num - 1,
            }
            for key in (
                "coqview_scheduled_steps",
                "coqview_local_rule_len",
                "coqview_global_rule_len",
                "coqview_active_targets",
                "coqview_global_active_targets",
                "coqview_rank_active_targets",
                "coqview_rank_loss_sums",
                "coqview_loss_scale",
                "coqview_sync_last_only",
                "coqview_eval_mode_for_loss",
                "coqview_skip_backward_for_debug",
                "coqview_manual_distributed",
                "coqview_history_gradient_policy",
                "distributed_zero_loss_padding_rows",
                "global_distributed_zero_loss_padding_rows",
                "rank_distributed_zero_loss_padding_rows",
                "local_rank_loss",
                "global_token_weighted_loss",
                "global_active_target_tokens",
                "rank_active_target_tokens",
                "rank_losses",
                "distributed_token_mean_backward_scale",
                "active_targets",
                "coq_gate",
            ):
                if key in info:
                    batch_metrics[key] = info[key]
            logger.log(batch_metrics)
            if epoch % args.eval_step == 0 and epoch >= args.eval_step_init:
                logger.log({
                    "loss_eval": metric_loss,
                    "epoch": epoch,
                    "batch": batch_num - 1,
                })
            if "sigma1" in info:
                logger.log({"sigma1": info["sigma1"].item(), "sigma2": info["sigma2"].item()})
                logger.log({"loss1": info["loss1"].item(), "loss2": info["loss2"].item()})
            if args.limit_train_batches and batch_num >= args.limit_train_batches:
                break
        logger.log({"runtime": tot_runtime / batch_num, "epoch": epoch})
        if epoch % args.empty_cuda_cache == 0:
            torch.cuda.empty_cache()
    accelerator.wait_for_everyone()
    if accelerator.is_main_process:
        unwrapped_model = accelerator.unwrap_model(model)
        root_model_dir = f"Utils/models/Model{model_output_task}/"
        final_model_dir = f"Utils/models/Model{model_output_task}/{date}/"
        save_model(unwrapped_model, root_model_dir, model_type="last")
        if not args.save_last_only:
            snapshot_saved_model(root_model_dir, "last", final_model_dir, "final")
    accelerator.wait_for_everyone()
    logger.finish()
    accelerator.end_training()

@torch.no_grad()
def evalmodel(dev_set, model, device, accelerator, newruledic):
    load_beam_searches()
    batch_size = args.batch_size
    data_offset = sum(commu.get("valid_data_len")[:accelerator.process_index])
    data_loader = torch.utils.data.DataLoader(
        dataset=dev_set,
        batch_size=batch_size,
        drop_last=False,
        num_workers=args.eval_num_workers,
        collate_fn=rs_collate_fn,
        shuffle=False,
        pin_memory=True,
    )
    beamsize = 3
    if "coq" in args.task or "grammar" in args.task:
        beam = BeamSearchCoq(
            beamsize,
            newruledic,
            tokenizer_obj=load_tokenizer_for_task(args.task),
            checkcoq=False,
            candidate_multiplier=args.coq_candidate_multiplier,
        )
    elif "nocheck" in args.task:
        beam = BeamSearchCoq(beamsize, newruledic, tokenizer_obj=load_tokenizer_for_task(args.task), checkcoq=False, check_grammar=False)
    elif "dsl" in args.task:
        beam = BeamSearchDsl(beamsize, newruledic)
    else:
        beam = BeamSearch(beamsize, newruledic)

    model.eval()
    f = open("tmp/out_val%d.txt" % int(accelerator.process_index), "w")
    for index,dBatch in enumerate(data_loader):
        batch_len = len(dBatch["nl"])
        offset = data_offset + index * batch_size
        dBatch["nl"] = dBatch["nl"].to(device).repeat_interleave(beamsize, dim=0)
        with accelerator.autocast():
            ans = beam.search(
                dBatch["nl"], model, max_len=args.CodeLen,
                desc=f"Problem {offset}-{offset+batch_len-1}", offset=offset
            )
        for i in range(len(ans)):
            try:
                code = ans[i].final_set[0]
                # remove annotations and \n
                code = " ".join([line for line in code.split("\n") if not line.strip().startswith("//")])
            except IndexError as e:
                code = f"IndexError: {e}"
            f.write(code + "\n")
    f.close()

    accelerator.wait_for_everyone()
    if accelerator.is_main_process:
        os.system(": > tmp/out.txt")
        for i in range(accelerator.num_processes):
            os.system("cat tmp/out_val%d.txt >> tmp/out.txt" % i)
        tnum, codebelu = calc_code_bleu.get_codebleu(
            f"Utils/data/{args.task}/groundvalid.txt",
            "tmp/out.txt",
            "java",
            benchmark=args.task,
        )
        return tnum, codebelu
    else:
        return 0, 0

@torch.no_grad()
def testmodel(data_set, model, device, accelerator, newruledic):
    load_beam_searches()
    batch_size = args.batch_size_eval 
    tasktype = data_set.dataName # valid or test
    shard_lengths = commu.get(f"{tasktype}_data_len")
    data_offset = sum(shard_lengths[:accelerator.process_index])
    requested_indices = parse_int_list(args.get("eval_indices", ""))
    if requested_indices:
        problem_id_shards = commu.get(f"{tasktype}_problem_ids")
        selected_problem_ids = [int(value) for value in problem_id_shards[accelerator.process_index]]
        if len(selected_problem_ids) != len(data_set.data):
            raise RuntimeError("preselected eval row/id shard length mismatch")
    else:
        selected_problem_ids = list(range(data_offset, data_offset + len(data_set.data)))
    if requested_indices and (args.eval_start or args.eval_limit):
        raise ValueError("eval_indices cannot be combined with eval_start/eval_limit")
    if not requested_indices and (args.eval_start or args.eval_limit) and hasattr(data_set, "data"):
        local_start, local_end, selected_offset = distributed_eval_range_slice(
            shard_start=data_offset,
            shard_length=len(data_set.data),
            global_length=sum(shard_lengths),
            eval_start=args.eval_start,
            eval_limit=args.eval_limit,
        )
        data_set.data = data_set.data[local_start:local_end]
        data_offset = selected_offset
        selected_problem_ids = list(
            range(selected_offset, selected_offset + len(data_set.data))
        )
    print(f"Task type: {tasktype}")
    data_loader = torch.utils.data.DataLoader(
        dataset=data_set,
        batch_size=batch_size,
        drop_last=False,
        num_workers=args.eval_num_workers,
        collate_fn=rs_collate_fn,
        shuffle=False,
        pin_memory=True,
    )
    
    beamsize = int(args.get("beam_size", 10))
    if beamsize < 1:
        raise ValueError(f"beam_size must be positive, got {beamsize}")
    eval_max_len = resolve_eval_decode_max_len(args)
    if "sufu" in args.task:
        sufu_decoder_options = resolve_sufu_decoder_options(args)
        beam = BeamSearchSufu(beamsize, newruledic, tokenizer_obj=load_tokenizer_for_task(args.task), type_ctx_len=args.max_coqview_len,
                              length_penalty=args.length_penalty,
                              type_check=sufu_decoder_options["type_check"],
                              add_type_ctx=sufu_decoder_options["add_type_ctx"],
                              check_grammar=(
                                  not args.get("disable_sufu_grammar", False)
                              ),
                              candidate_multiplier=args.coq_candidate_multiplier,
                              disable_tqdm=args.disable_tqdm)
    # mbjp humaneval
    elif args.enable_coqview:
        beam = BeamSearchCoq(
            beamsize,
            newruledic,
            tokenizer_obj=load_tokenizer_for_task(args.task),
            coqview_len=args.max_coqview_len,
            addCoqview=True,
            candidate_multiplier=args.coq_candidate_multiplier,
            coq_workers=args.coq_workers,
            coq_timeout=args.coq_timeout,
            length_penalty=args.length_penalty,
            early_stop_after_final_steps=args.early_stop_after_final_steps,
            early_stop_max_first_final_len=args.early_stop_max_first_final_len,
            disable_tqdm=args.disable_tqdm,
        )
    elif args.get("force_coq_decoder", False) or "coq" in args.task:
        beam = BeamSearchCoq(
            beamsize,
            newruledic,
            tokenizer_obj=load_tokenizer_for_task(args.task),
            checkcoq=not args.get("disable_coq_check", False),
            final_only_coq_check=args.get("coq_final_only_check", False),
            candidate_multiplier=args.coq_candidate_multiplier,
            coq_workers=args.coq_workers,
            coq_timeout=args.coq_timeout,
            length_penalty=args.length_penalty,
            early_stop_after_final_steps=args.early_stop_after_final_steps,
            early_stop_max_first_final_len=args.early_stop_max_first_final_len,
            disable_tqdm=args.disable_tqdm,
        )
    elif "grammar" in args.task:
        beam = BeamSearchCoq(
            beamsize,
            newruledic,
            tokenizer_obj=load_tokenizer_for_task(args.task),
            checkcoq=False,
            candidate_multiplier=args.coq_candidate_multiplier,
            coq_workers=args.coq_workers,
            coq_timeout=args.coq_timeout,
            length_penalty=args.length_penalty,
            early_stop_after_final_steps=args.early_stop_after_final_steps,
            early_stop_max_first_final_len=args.early_stop_max_first_final_len,
            disable_tqdm=args.disable_tqdm,
        )
    elif "nocheck" in args.task:
        beam = BeamSearchCoq(beamsize, newruledic, tokenizer_obj=load_tokenizer_for_task(args.task), checkcoq=False, check_grammar=False)
    elif "dsl" in args.task:
        beam = BeamSearchDsl(beamsize, newruledic)
    else:
        beam = BeamSearch(beamsize, newruledic)
    
    target_folder = f"Utils/output/{args.task}_{tasktype}_ans/"
    if args.output_tag:
        target_folder += f"{args.output_tag}/"
    elif args.train_time:
        target_folder += f"{args.train_time}/{args.checkpoint_epoch}/"
    if accelerator.is_main_process:
        if os.path.exists(target_folder) and not args.resume_output:
            shutil.rmtree(target_folder)
        os.makedirs(target_folder, exist_ok=args.resume_output)

    accelerator.wait_for_everyone()
    model.eval()
    for index, dBatch in enumerate(data_loader):
        batch_len = len(dBatch["nl"])
        batch_problem_ids = selected_problem_ids[
            index * batch_size : index * batch_size + batch_len
        ]
        if args.resume_output:
            all_done = True
            for problem_id in batch_problem_ids:
                for k in range(beamsize):
                    if not output_candidate_complete(f"{target_folder}{problem_id}_{k}.txt"):
                        all_done = False
                        break
                if not all_done:
                    break
            if all_done:
                print(f"{batch_problem_ids} already exist in {target_folder}")
                continue
        with accelerator.autocast():
            ans = beam.search(
                dBatch["nl"].to(device).repeat_interleave(beamsize, dim=0),
                model,
                max_len=eval_max_len,
                desc=f"Problems {batch_problem_ids}",
                offset=batch_problem_ids[0] if batch_problem_ids else 0,
                problem_ids=batch_problem_ids,
                init_tokens=dBatch["prefix"].to(device) if "prefix" in dBatch else None,
            )
        for i in range(len(ans)):
            problem_id = batch_problem_ids[i]
            for k in range(beamsize):
                file_path = f"{target_folder}{problem_id}_{k}.txt"
                if k >= len(ans[i].final_set):
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    continue
                with open(file_path, "w") as f:
                    f.write(ans[i].final_set[k])
            if hasattr(ans[i], "final_metadata"):
                score_path = f"{target_folder}{problem_id}_beam_scores.json"
                with open(score_path, "w") as f:
                    json.dump(
                        {
                            "problem_id": problem_id,
                            "beam_size": beamsize,
                            "candidates": ans[i].final_metadata,
                        },
                        f,
                        indent=2,
                        sort_keys=True,
                    )
        print(f"{batch_problem_ids} saved to {target_folder}")
                  
if __name__ == "__main__":
    np.set_printoptions(threshold=sys.maxsize)
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", type=str, required=True)
    parser.add_argument("--eval", action="store_true")
    parser.add_argument("--train_time", type=str, default="")
    parser.add_argument("--checkpoint_epoch", type=int, default=200)
    parser.add_argument("--no_swanlab", action="store_true")
    parser.add_argument("--include_debug", action="store_true", default=None)
    parser.add_argument("--max_epoch", type=int)
    parser.add_argument("--epoch_offset", type=int)
    parser.add_argument("--batch_size", type=int)
    parser.add_argument("--batch_size_eval", type=int)
    parser.add_argument("--lr", type=float)
    parser.add_argument("--pretrain_name", type=str)
    parser.add_argument("--pretrain_model_type", type=str)
    parser.add_argument("--eval_step", type=int)
    parser.add_argument("--eval_step_init", type=int)
    parser.add_argument("--limit_train_batches", type=int, default=0)
    parser.add_argument("--metrics_file", type=str, default="")
    parser.add_argument("--tensorboard_dir", type=str, default="")
    parser.add_argument("--output_tag", type=str, default="")
    parser.add_argument("--model_output_task", type=str, default="")
    parser.add_argument("--model_type", type=str)
    parser.add_argument("--runtime_dir", type=str, default="")
    parser.add_argument("--coq_candidate_multiplier", type=int)
    parser.add_argument("--coq_workers", type=int)
    parser.add_argument("--coq_timeout", type=int)
    parser.add_argument(
        "--disable_coq_check",
        action=argparse.BooleanOptionalAction,
        default=None,
    )
    parser.add_argument("--coq_final_only_check", action="store_true", default=None)
    parser.add_argument("--length_penalty", type=float)
    parser.add_argument("--beam_size", type=int)
    parser.add_argument("--early_stop_after_final_steps", type=int)
    parser.add_argument("--early_stop_max_first_final_len", type=int)
    parser.add_argument("--eval_split", type=str, choices=["train", "valid", "test"], default="test")
    parser.add_argument("--eval_start", type=int)
    parser.add_argument("--eval_limit", type=int)
    parser.add_argument("--eval_indices", type=str)
    parser.add_argument("--eval_max_len", type=int)
    parser.add_argument("--resume_output", action="store_true", default=None)
    parser.add_argument("--disable_tqdm", action="store_true", default=None)
    parser.add_argument("--force_coq_decoder", action="store_true", default=None)
    parser.add_argument("--force_sufu_type_check", action="store_true", default=None)
    parser.add_argument("--disable_sufu_grammar", action="store_true", default=None)
    parser.add_argument("--save_last_only", action="store_true", default=None)
    parser.add_argument("--pad_train_shards_to_equal_batches", action="store_true", default=None)
    parser.add_argument("--train_num_workers", type=int)
    parser.add_argument("--eval_num_workers", type=int)
    parser.add_argument("--distributed_timeout_minutes", type=int)
    parser.add_argument("--ddp_find_unused_parameters", action="store_true", default=None)
    parser.add_argument("--coqview_suffix_replay_steps", type=int)
    parser.add_argument("--coqview_suffix_replay_repeats", type=int)
    parser.add_argument("--coqview_extra_window_offsets", type=str)
    parser.add_argument("--coqview_extra_window_steps", type=int)
    parser.add_argument("--coqview_extra_window_repeats", type=int)
    parser.add_argument("--coqview_loss_reduction", choices=["sum", "mean"])
    parser.add_argument("--coqview_sync_last_only", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--coqview_eval_mode_for_loss", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--coqview_skip_backward_for_debug", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--coqview_manual_distributed", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--train_only_expanded_embedding_rows", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--base_vocab_rows", type=int)
    parser.add_argument("--coq_feature_lr", type=float)
    parser.add_argument("--coq_feature_only", action=argparse.BooleanOptionalAction, default=None)
    argc = parser.parse_args()
    # mbjp, mbjp_blind, mbjpcoq, mbjpcoqview, mbjp_dsl, mbjpcoq_770m, mbjpcoqview_770m
    # humaneval_blind, humanevalcoq, humanevalcoqview
    # sufugrammar, sufucoq, sufucoqview
    # pretrain, pretrain_770m
    args.task = argc.task 
    if argc.eval:
        args.eval = True
        args.train_time = argc.train_time
        args.checkpoint_epoch = argc.checkpoint_epoch
    args.no_swanlab = argc.no_swanlab
    override_keys = ["max_epoch", "epoch_offset", "batch_size", "batch_size_eval", "lr", "coq_feature_lr", "coq_feature_only", "pretrain_name", "pretrain_model_type", "eval_step", "eval_step_init", "limit_train_batches", "metrics_file", "tensorboard_dir", "output_tag", "model_output_task", "model_type", "runtime_dir", "coq_candidate_multiplier", "coq_workers", "coq_timeout", "disable_coq_check", "coq_final_only_check", "length_penalty", "beam_size", "early_stop_after_final_steps", "early_stop_max_first_final_len", "eval_split", "eval_start", "eval_limit", "eval_indices", "eval_max_len", "resume_output", "disable_tqdm", "force_coq_decoder", "force_sufu_type_check", "disable_sufu_grammar", "save_last_only", "pad_train_shards_to_equal_batches", "train_num_workers", "eval_num_workers", "distributed_timeout_minutes", "ddp_find_unused_parameters", "coqview_suffix_replay_steps", "coqview_suffix_replay_repeats", "coqview_extra_window_offsets", "coqview_extra_window_steps", "coqview_extra_window_repeats", "coqview_loss_reduction", "coqview_sync_last_only", "coqview_eval_mode_for_loss", "coqview_skip_backward_for_debug", "coqview_manual_distributed", "train_only_expanded_embedding_rows", "base_vocab_rows", "include_debug"]
    args.cli_overrides = {key: getattr(argc, key) for key in override_keys if getattr(argc, key) is not None}
    finetune()
