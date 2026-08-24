#!/usr/bin/env bash
# Train the ordinary T5Gemma2-2B baseline on the clean 673-row Java split.

set -euo pipefail

cd /data2/x/hzc/prooft5

PLAIN_PY=/data2/x/hzc/.uv-envs/prooft5-t5gemma-py313/bin/python
PLAIN_GPU="${CLEAN_JAVA_PLAIN_GPU:-0}"
PLAIN_PASSES="${CLEAN_JAVA_PLAIN_PASSES:-30}"
PLAIN_LR="${CLEAN_JAVA_PLAIN_LR:-5e-5}"
PLAIN_BATCH_SIZE="${CLEAN_JAVA_PLAIN_BATCH_SIZE:-5}"
PLAIN_STAMP="${CLEAN_JAVA_PLAIN_STAMP:-$(date -u +%Y%m%d_%H%M%S)}"
if ! [[ "$PLAIN_STAMP" =~ ^[A-Za-z0-9._-]+$ ]]; then
  printf 'CLEAN_JAVA_PLAIN_STAMP must be filename-safe\n' >&2
  exit 64
fi
PLAIN_TASK="t5gemma2-2b_java_clean673_noleak_b${PLAIN_BATCH_SIZE}_lr${PLAIN_LR//-/m}_pass${PLAIN_PASSES}_${PLAIN_STAMP}"
PLAIN_RUN="${PLAIN_STAMP}"
PLAIN_LOG="tmp/${PLAIN_TASK}.log"
PLAIN_MODEL_ROOT="t5_llm/models/${PLAIN_TASK}"
PLAIN_DATA_ROOT="Utils/data/${PLAIN_TASK}"

if ! [[ "$PLAIN_PASSES" =~ ^[1-9][0-9]*$ ]]; then
  printf 'CLEAN_JAVA_PLAIN_PASSES must be a positive integer\n' >&2
  exit 64
fi
if ! [[ "$PLAIN_BATCH_SIZE" =~ ^[1-9][0-9]*$ ]]; then
  printf 'CLEAN_JAVA_PLAIN_BATCH_SIZE must be a positive integer\n' >&2
  exit 64
fi
for path in "$PLAIN_LOG" "$PLAIN_MODEL_ROOT" "$PLAIN_DATA_ROOT"; do
  if [ -e "$path" ]; then
    printf 'refusing to overwrite training artifact: %s\n' "$path" >&2
    exit 73
  fi
done

PLAIN_USED="$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i "$PLAIN_GPU" | tr -d ' ')"
if [ "$PLAIN_USED" -ge 1024 ]; then
  printf 'GPU %s is occupied (%s MiB); no training artifact was created\n' \
    "$PLAIN_GPU" "$PLAIN_USED" >&2
  exit 75
fi

"$PLAIN_PY" t5_llm/finetune_t5gemma2.py \
  --dataset java_expanded_train --task_name "$PLAIN_TASK" --dry_run \
  --local_files_only | tee "$PLAIN_LOG"
if ! grep -q 'Train/valid/test: 673/0/0' "$PLAIN_LOG"; then
  printf 'clean split preflight did not report 673/0/0\n' >&2
  exit 65
fi
if grep -q 'debug-only training data' "$PLAIN_LOG"; then
  printf 'debug-overlap data unexpectedly entered the training split\n' >&2
  exit 65
fi

printf '[%s] task=%s gpu=%s passes=%s batch=%s lr=%s\n' \
  "$(date -Iseconds)" "$PLAIN_TASK" "$PLAIN_GPU" "$PLAIN_PASSES" \
  "$PLAIN_BATCH_SIZE" "$PLAIN_LR" | tee -a "$PLAIN_LOG"

CUDA_VISIBLE_DEVICES="$PLAIN_GPU" \
TOKENIZERS_PARALLELISM=false \
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
"$PLAIN_PY" -u t5_llm/finetune_t5gemma2.py \
  --dataset java_expanded_train --task_name "$PLAIN_TASK" \
  --run_name "$PLAIN_RUN" --cuda 0 --batch_size "$PLAIN_BATCH_SIZE" \
  --lr "$PLAIN_LR" --max_epochs "$((PLAIN_PASSES - 1))" \
  --checkpoint_every_epochs 5 --checkpoint_start_epoch 4 \
  --bf16 --no_swanlab --skip_test_during_eval --skip_final_generation \
  --local_files_only 2>&1 | tee -a "$PLAIN_LOG"

if [ ! -f "$PLAIN_MODEL_ROOT/config.json" ]; then
  printf 'final ordinary-model checkpoint is absent: %s\n' "$PLAIN_MODEL_ROOT" >&2
  exit 66
fi
EXPECTED_INTERMEDIATE_CHECKPOINTS="$(( (PLAIN_PASSES - 1) / 5 ))"
ACTUAL_INTERMEDIATE_CHECKPOINTS="$(
  find "$PLAIN_MODEL_ROOT/$PLAIN_RUN" -mindepth 1 -maxdepth 1 \
    -type d -name 'epoch_*' | wc -l
)"
if [ "$ACTUAL_INTERMEDIATE_CHECKPOINTS" -ne "$EXPECTED_INTERMEDIATE_CHECKPOINTS" ]; then
  printf 'expected %s intermediate five-pass checkpoints under %s, found %s\n' \
    "$EXPECTED_INTERMEDIATE_CHECKPOINTS" "$PLAIN_MODEL_ROOT/$PLAIN_RUN" \
    "$ACTUAL_INTERMEDIATE_CHECKPOINTS" >&2
  exit 65
fi

printf '[%s] complete: model=%s\n' "$(date -Iseconds)" "$PLAIN_MODEL_ROOT" | \
  tee -a "$PLAIN_LOG"
