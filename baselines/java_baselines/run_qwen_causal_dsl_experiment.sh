#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 1 ]; then
  echo "usage: $0 <train_plain|train_coqview|eval_plain|eval_coqview> [run.py args...]" >&2
  exit 2
fi

ACTION="$1"
shift
ACCELERATE="${PROOFT5_QWEN_ACCELERATE:-/data2/x/hzc/.uv-envs/prooft5-t5gemma-py313/bin/accelerate}"
PROCESSES="${PROOFT5_QWEN_PROCESSES:-3}"
GPUS="${PROOFT5_QWEN_GPUS:-0,1,2}"
PORT="${PROOFT5_QWEN_PORT:-29500}"
STAMP="20260825"

case "$ACTION" in
  train_plain)
    TASK="pretrain_qwen25coder3b_java_clean673_plain_${STAMP}"
    MODEL_OUTPUT_TASK="qwen25coder3b_java_clean673_plain_${STAMP}"
    METRICS="artifacts/major_revision_decoder_only_${STAMP}/plain_train_metrics.jsonl"
    ;;
  train_coqview)
    TASK="pretrain_qwen25coder3b_java_clean673_coqview_${STAMP}"
    MODEL_OUTPUT_TASK="qwen25coder3b_java_clean673_coqview_featureonly_zeroinit_lr1e5_${STAMP}"
    METRICS="artifacts/major_revision_decoder_only_${STAMP}/coqview_featureonly_zeroinit_lr1e5_train_metrics.jsonl"
    ;;
  eval_plain)
    TASK="qwen25coder3b_mbjp_plain_eval_${STAMP}"
    MODEL_OUTPUT_TASK="qwen25coder3b_java_clean673_plain_${STAMP}"
    METRICS=""
    ;;
  eval_coqview)
    TASK="qwen25coder3b_mbjp_coqview_eval_${STAMP}"
    MODEL_OUTPUT_TASK="qwen25coder3b_java_clean673_coqview_featureonly_zeroinit_lr1e5_${STAMP}"
    METRICS=""
    ;;
  *)
    echo "unknown action: $ACTION" >&2
    exit 2
    ;;
esac

mkdir -p "artifacts/major_revision_decoder_only_${STAMP}"
COMMON=(
  --task "$TASK"
  --model_output_task "$MODEL_OUTPUT_TASK"
  --runtime_dir "tmp/runtime_state/${MODEL_OUTPUT_TASK}"
  --no_swanlab
  --distributed_timeout_minutes 180
)

if [[ "$ACTION" == train_* ]]; then
  COMMON+=(--metrics_file "$METRICS")
else
  COMMON+=(
    --eval
    --eval_split test
    --model_type selected
    --beam_size 10
    --length_penalty 0.1
    --disable_tqdm
    --resume_output
    --output_tag "formal_${ACTION}_${STAMP}"
  )
  if [ "$ACTION" = eval_plain ]; then
    COMMON+=(--disable_coq_check)
  fi
fi

CUDA_VISIBLE_DEVICES="$GPUS" "$ACCELERATE" launch \
  --num_processes "$PROCESSES" \
  --main_process_port "$PORT" \
  --mixed_precision bf16 \
  run.py "${COMMON[@]}" "$@"
