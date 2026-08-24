#!/usr/bin/env bash
# Launch a fully auditable, no-validation CoqView training run.
#
# Usage:
#   scripts/run_complete_coqview_training.sh TASK PARENT_TASK java|sufu
#
# TASK is the already-built CoqView data task. PARENT_TASK is the selected
# T5Gemma2 model name *without* the leading "Model" directory prefix. By
# default it must be the direct parent pinned in the task config. For an
# audited weight-only continuation, set COQVIEW_EPOCH_OFFSET to the number of
# already completed passes and use the preceding CoqView run as PARENT_TASK.

set -euo pipefail

if [ "$#" -ne 3 ]; then
  printf 'usage: %s TASK PARENT_TASK java|sufu\n' "$0" >&2
  exit 64
fi

COQVIEW_TASK="$1"
COQVIEW_PARENT="$2"
COQVIEW_BRANCH="$3"
case "$COQVIEW_BRANCH" in java|sufu) ;; *) printf 'branch must be java or sufu\n' >&2; exit 64 ;; esac

cd /data2/x/hzc/prooft5

# The historical gate-selection ledgers chose different learning rates, then
# the formal launcher restarted both branches from their direct parents for
# ten passes. Environment overrides remain available for explicit gate runs.
COQVIEW_RUN_PASSES="${COQVIEW_RUN_PASSES:-10}"
COQVIEW_EPOCH_OFFSET="${COQVIEW_EPOCH_OFFSET:-0}"
if [ "$COQVIEW_BRANCH" = "java" ]; then
  COQVIEW_RUN_LR="${COQVIEW_RUN_LR:-1e-6}"
else
  COQVIEW_RUN_LR="${COQVIEW_RUN_LR:-5e-6}"
fi
COQVIEW_RUN_GPUS="${COQVIEW_RUN_GPUS:-0,1,2,3,4,5,6,7}"
COQVIEW_RUN_PORT="${COQVIEW_RUN_PORT:-29681}"
COQVIEW_MAX_USED_MIB="${COQVIEW_MAX_USED_MIB:-1024}"
if ! [[ "$COQVIEW_RUN_PASSES" =~ ^[1-9][0-9]*$ ]]; then
  printf 'COQVIEW_RUN_PASSES must be a positive integer\n' >&2
  exit 64
fi
if ! [[ "$COQVIEW_EPOCH_OFFSET" =~ ^[0-9]+$ ]]; then
  printf 'COQVIEW_EPOCH_OFFSET must be a non-negative integer\n' >&2
  exit 64
fi

IFS=',' read -r -a COQVIEW_GPU_ARRAY <<< "$COQVIEW_RUN_GPUS"
COQVIEW_NUM_PROCESSES="${#COQVIEW_GPU_ARRAY[@]}"
if [ "$COQVIEW_NUM_PROCESSES" -lt 1 ]; then
  printf 'at least one GPU id is required, got: %s\n' "$COQVIEW_RUN_GPUS" >&2
  exit 64
fi

COQVIEW_EPOCH_MAX=$((COQVIEW_RUN_PASSES - 1))
COQVIEW_EPOCH_END=$((COQVIEW_EPOCH_OFFSET + COQVIEW_RUN_PASSES))
COQVIEW_STAMP="${COQVIEW_RUN_STAMP:-$(date -u +%Y%m%d_%H%M%S)}"
COQVIEW_LR_TAG="${COQVIEW_RUN_LR//-/m}"
if [ "$COQVIEW_EPOCH_OFFSET" -eq 0 ]; then
  COQVIEW_PASS_TAG="pass${COQVIEW_RUN_PASSES}"
else
  COQVIEW_PASS_TAG="pass${COQVIEW_EPOCH_OFFSET}to${COQVIEW_EPOCH_END}"
fi
COQVIEW_TAG="${COQVIEW_TASK}_${COQVIEW_BRANCH}_fullseq_b1_lr${COQVIEW_LR_TAG}_${COQVIEW_PASS_TAG}_${COQVIEW_STAMP}"
COQVIEW_PARENT_PATH="Utils/models/Model${COQVIEW_PARENT}/last_model.ckpt"
COQVIEW_LOG="tmp/${COQVIEW_TAG}.log"
COQVIEW_METRICS="tmp/${COQVIEW_TAG}_metrics.jsonl"
COQVIEW_TENSORBOARD="Utils/tensorboard/${COQVIEW_TASK}/${COQVIEW_TAG}"
COQVIEW_RUNTIME="tmp/runtime_state/${COQVIEW_TAG}"
COQVIEW_PY="/data2/x/hzc/.uv-envs/prooft5-t5gemma-py313/bin/python"
COQVIEW_ACC="/data2/x/hzc/.uv-envs/prooft5-t5gemma-py313/bin/accelerate"

if [ ! -f "$COQVIEW_PARENT_PATH" ]; then
  printf 'selected parent checkpoint is absent: %s\n' "$COQVIEW_PARENT_PATH" >&2
  exit 66
fi
for COQVIEW_PATH in "Utils/data/${COQVIEW_TASK}" "Utils/models/Model${COQVIEW_TAG}" "$COQVIEW_LOG" "$COQVIEW_METRICS" "$COQVIEW_TENSORBOARD" "$COQVIEW_RUNTIME"; do
  if [ -e "$COQVIEW_PATH" ] && [ "$COQVIEW_PATH" != "Utils/data/${COQVIEW_TASK}" ]; then
    printf 'refusing to overwrite run artifact: %s\n' "$COQVIEW_PATH" >&2
    exit 73
  fi
done

"$COQVIEW_PY" - "$COQVIEW_TASK" "$COQVIEW_PARENT" "$COQVIEW_EPOCH_OFFSET" <<'PY'
import json
import pickle
import sys
from pathlib import Path

task, parent, epoch_offset_text = sys.argv[1:]
epoch_offset = int(epoch_offset_text)
root = Path("Utils/data") / task
if not root.is_dir():
    raise SystemExit(f"missing CoqView task: {root}")
config = json.loads((root / "config.json").read_text())
configured_parent = config.get("pretrain_name")
if config.get("pretrain_model_type") != "last":
    raise SystemExit("task must pin the last checkpoint of its direct parent")
if epoch_offset == 0:
    if configured_parent != parent:
        raise SystemExit("fresh run is not pinned to the selected direct parent")
else:
    if configured_parent == parent:
        raise SystemExit("continuation parent unexpectedly equals the direct parent")
    if not parent.startswith(task + "_"):
        raise SystemExit("continuation parent is not a prior run of this CoqView task")
if not config.get("enable_coqview") or config.get("validation"):
    raise SystemExit("task must be CoqView with validation disabled")
with (root / "valid.pkl").open("rb") as handle:
    if pickle.load(handle):
        raise SystemExit("valid.pkl must be empty")
for split in ("train", "test"):
    with (root / f"{split}.pkl").open("rb") as handle:
        rows = pickle.load(handle)
    if split == "train" and not rows:
        raise SystemExit("train is empty")
    if any("coqview" not in row for row in rows):
        raise SystemExit(f"{split} has a row without CoqView contexts")
print({
    "task": task,
    "parent": parent,
    "epoch_offset": epoch_offset,
    "train_rows": len(pickle.load((root / "train.pkl").open("rb"))),
    "valid_rows": 0,
    "test_rows": len(pickle.load((root / "test.pkl").open("rb"))),
})
PY

for COQVIEW_GPU in "${COQVIEW_GPU_ARRAY[@]}"; do
  COQVIEW_USED="$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i "$COQVIEW_GPU" | tr -d ' ')"
  if [ "$COQVIEW_USED" -ge "$COQVIEW_MAX_USED_MIB" ]; then
    printf 'GPU %s is occupied (%s MiB); no artifact was created\n' "$COQVIEW_GPU" "$COQVIEW_USED" >&2
    exit 75
  fi
done

printf '[%s] tag=%s\n' "$(date -Iseconds)" "$COQVIEW_TAG" | tee "$COQVIEW_LOG"
printf '[%s] task=%s parent=%s branch=%s passes=%s epoch_offset=%s lr=%s\n' \
  "$(date -Iseconds)" "$COQVIEW_TASK" "$COQVIEW_PARENT" "$COQVIEW_BRANCH" "$COQVIEW_RUN_PASSES" "$COQVIEW_EPOCH_OFFSET" "$COQVIEW_RUN_LR" | tee -a "$COQVIEW_LOG"
sha256sum "$COQVIEW_PARENT_PATH" | tee -a "$COQVIEW_LOG"

CUDA_VISIBLE_DEVICES="$COQVIEW_RUN_GPUS" \
OMP_NUM_THREADS=8 MKL_NUM_THREADS=8 OPENBLAS_NUM_THREADS=8 NUMEXPR_NUM_THREADS=8 \
TOKENIZERS_PARALLELISM=false \
PROOFT5_DISTRIBUTED_TIMEOUT_MINUTES=720 \
TORCH_NCCL_HEARTBEAT_TIMEOUT_SEC=7200 \
TORCH_NCCL_ASYNC_ERROR_HANDLING=1 \
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
"$COQVIEW_ACC" launch \
  --config_file tmp/acc_config_ddp_bf16.yaml \
  --num_processes "$COQVIEW_NUM_PROCESSES" \
  --main_process_port "$COQVIEW_RUN_PORT" \
  run.py \
  --task "$COQVIEW_TASK" \
  --pretrain_name "$COQVIEW_PARENT" \
  --pretrain_model_type last \
  --no_swanlab \
  --model_output_task "$COQVIEW_TAG" \
  --runtime_dir "$COQVIEW_RUNTIME" \
  --distributed_timeout_minutes 720 \
  --max_epoch "$COQVIEW_EPOCH_MAX" \
  --epoch_offset "$COQVIEW_EPOCH_OFFSET" \
  --batch_size 1 \
  --batch_size_eval 1 \
  --lr "$COQVIEW_RUN_LR" \
  --eval_step 1 \
  --eval_step_init 0 \
  --train_num_workers 0 \
  --eval_num_workers 0 \
  --pad_train_shards_to_equal_batches \
  --coqview_loss_reduction mean \
  --coqview_sync_last_only \
  --coqview_manual_distributed \
  --metrics_file "$COQVIEW_METRICS" \
  --tensorboard_dir "$COQVIEW_TENSORBOARD" \
  2>&1 | tee -a "$COQVIEW_LOG"

printf '[%s] complete: checkpoints are in Utils/models/Model%s\n' \
  "$(date -Iseconds)" "$COQVIEW_TAG" | tee -a "$COQVIEW_LOG"
