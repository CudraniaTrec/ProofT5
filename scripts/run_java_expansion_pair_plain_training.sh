#!/usr/bin/env bash
# Train one benchmark-specific ordinary T5Gemma2 route from a frozen parent.

set -euo pipefail

cd /data2/x/hzc/prooft5

if [ "$#" -ne 3 ]; then
  printf 'usage: %s SOURCE_TASK MODEL_TASK RUN_NAME\n' "$0" >&2
  exit 64
fi

SOURCE_TASK="$1"
MODEL_TASK="$2"
RUN_NAME="$3"
PLAIN_GPU="${JAVA_PAIR_PLAIN_GPU:-0}"
PLAIN_MAX_USED_MIB="${JAVA_PAIR_PLAIN_MAX_USED_MIB:-1024}"
PLAIN_PASSES="${JAVA_PAIR_PLAIN_PASSES:-10}"
PLAIN_LR="${JAVA_PAIR_PLAIN_LR:-5e-6}"
PLAIN_BATCH_SIZE="${JAVA_PAIR_PLAIN_BATCH_SIZE:-5}"
PLAIN_PARENT="${JAVA_PAIR_PLAIN_PARENT:-t5_llm/models/paper_comparison_20260731/t5gemma2-2b_mbjp}"
PLAIN_TOKENIZER="${JAVA_PAIR_PLAIN_TOKENIZER:-Utils/models/t5gemma-2-1b-1b}"
PLAIN_TARGET_MODE="${JAVA_PAIR_PLAIN_TARGET_MODE:-full}"
PLAIN_PY=/data2/x/hzc/.uv-envs/prooft5-t5gemma-py313/bin/python

SOURCE_FILE="Utils/data/${SOURCE_TASK}/train_t5_plain_format.json"
MODEL_ROOT="t5_llm/models/${MODEL_TASK}"
TASK_DATA_ROOT="Utils/data/${MODEL_TASK}"
LOG_FILE="tmp/${MODEL_TASK}.log"

for value in "$SOURCE_TASK" "$MODEL_TASK" "$RUN_NAME"; do
  if ! [[ "$value" =~ ^[A-Za-z0-9._-]+$ ]]; then
    printf 'task and run names must be filename-safe: %s\n' "$value" >&2
    exit 64
  fi
done
if ! [[ "$PLAIN_PASSES" =~ ^[1-9][0-9]*$ ]]; then
  printf 'JAVA_PAIR_PLAIN_PASSES must be a positive integer\n' >&2
  exit 64
fi
if ! [[ "$PLAIN_BATCH_SIZE" =~ ^[1-9][0-9]*$ ]]; then
  printf 'JAVA_PAIR_PLAIN_BATCH_SIZE must be a positive integer\n' >&2
  exit 64
fi
if ! [[ "$PLAIN_MAX_USED_MIB" =~ ^[1-9][0-9]*$ ]]; then
  printf 'JAVA_PAIR_PLAIN_MAX_USED_MIB must be a positive integer\n' >&2
  exit 64
fi
if [[ "$PLAIN_TARGET_MODE" != "full" && "$PLAIN_TARGET_MODE" != "solution" ]]; then
  printf 'JAVA_PAIR_PLAIN_TARGET_MODE must be full or solution\n' >&2
  exit 64
fi
if [ ! -f "$SOURCE_FILE" ]; then
  printf 'source training file is absent: %s\n' "$SOURCE_FILE" >&2
  exit 66
fi
if [ ! -f "$PLAIN_PARENT/model.safetensors" ]; then
  printf 'frozen parent is absent: %s\n' "$PLAIN_PARENT" >&2
  exit 66
fi
if [ ! -f "$PLAIN_TOKENIZER/tokenizer.json" ]; then
  printf 'fixed T5Gemma2 tokenizer is absent: %s\n' "$PLAIN_TOKENIZER" >&2
  exit 66
fi
for path in "$MODEL_ROOT" "$TASK_DATA_ROOT" "$LOG_FILE"; do
  if [ -e "$path" ]; then
    printf 'refusing to overwrite training artifact: %s\n' "$path" >&2
    exit 73
  fi
done

PLAIN_USED="$(
  nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits \
    -i "$PLAIN_GPU" | tr -d ' '
)"
if [ "$PLAIN_USED" -ge "$PLAIN_MAX_USED_MIB" ]; then
  printf 'GPU %s is occupied (%s MiB); no training artifact was created\n' \
    "$PLAIN_GPU" "$PLAIN_USED" >&2
  exit 75
fi

"$PLAIN_PY" t5_llm/finetune_t5gemma2.py \
  --dataset java_expanded_train --dataset_file "$SOURCE_FILE" \
  --task_name "$MODEL_TASK" --model_path "$PLAIN_PARENT" \
  --tokenizer_path "$PLAIN_TOKENIZER" \
  --target_mode "$PLAIN_TARGET_MODE" \
  --dry_run --local_files_only | tee "$LOG_FILE"

EXPECTED_ROWS="$(jq 'length' "$SOURCE_FILE")"
if ! grep -q "Train/valid/test: ${EXPECTED_ROWS}/0/0" "$LOG_FILE"; then
  printf 'preflight did not report %s/0/0\n' "$EXPECTED_ROWS" >&2
  exit 65
fi
if grep -q 'debug-only training data' "$LOG_FILE"; then
  printf 'debug-overlap data unexpectedly entered the training split\n' >&2
  exit 65
fi

sha256sum "$PLAIN_PARENT/model.safetensors" | tee -a "$LOG_FILE"
printf 'PLAIN_SEED=273567\n' | tee -a "$LOG_FILE"
printf 'PLAIN_TARGET_MODE=%s\n' "$PLAIN_TARGET_MODE" | tee -a "$LOG_FILE"

CUDA_VISIBLE_DEVICES="$PLAIN_GPU" \
TOKENIZERS_PARALLELISM=false \
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
"$PLAIN_PY" -u t5_llm/finetune_t5gemma2.py \
  --dataset java_expanded_train --dataset_file "$SOURCE_FILE" \
  --task_name "$MODEL_TASK" --run_name "$RUN_NAME" \
  --model_path "$PLAIN_PARENT" --tokenizer_path "$PLAIN_TOKENIZER" --cuda 0 \
  --target_mode "$PLAIN_TARGET_MODE" \
  --batch_size "$PLAIN_BATCH_SIZE" --lr "$PLAIN_LR" \
  --max_epochs "$((PLAIN_PASSES - 1))" \
  --checkpoint_every_epochs 1 --checkpoint_start_epoch 0 \
  --bf16 --no_swanlab --skip_test_during_eval --skip_final_generation \
  --local_files_only 2>&1 | tee -a "$LOG_FILE"

EXPECTED_CHECKPOINTS="$PLAIN_PASSES"
ACTUAL_CHECKPOINTS="$(
  find "$MODEL_ROOT/$RUN_NAME" -mindepth 1 -maxdepth 1 \
    -type d -name 'epoch_*' | wc -l
)"
if [ "$ACTUAL_CHECKPOINTS" -ne "$EXPECTED_CHECKPOINTS" ]; then
  printf 'expected %s checkpoints, found %s\n' \
    "$EXPECTED_CHECKPOINTS" "$ACTUAL_CHECKPOINTS" >&2
  exit 65
fi
if [ ! -f "$MODEL_ROOT/config.json" ]; then
  printf 'final ordinary-model checkpoint is absent: %s\n' "$MODEL_ROOT" >&2
  exit 66
fi

printf '[%s] complete: model=%s\n' "$(date -Iseconds)" "$MODEL_ROOT" | \
  tee -a "$LOG_FILE"
