#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 1 ]; then
  echo "usage: $0 <train_plain|train_coq|eval_plain|eval_coq> [extra args...]" >&2
  exit 2
fi

ACTION="$1"
shift
PYTHON="${PROOFT5_QWEN_PYTHON:-/data2/x/hzc/.uv-envs/prooft5-t5gemma-py313/bin/python}"
ACCELERATE="${PROOFT5_QWEN_ACCELERATE:-/data2/x/hzc/.uv-envs/prooft5-t5gemma-py313/bin/accelerate}"
GPUS="${PROOFT5_QWEN_GPUS:-0,1,2,3,4,5,6,7}"
PROCESSES="${PROOFT5_QWEN_PROCESSES:-8}"
PORT="${PROOFT5_QWEN_PORT:-29520}"
DATA_STAMP="20260826"
RUN_ID="20260826_matchedseed19970316"
MODEL="Utils/models/Qwen2.5-3B"
PLAIN_MODEL_DIR="Utils/models/Qwen2.5-3B-Java-Plain-${RUN_ID}"
COQ_MODEL_TASK="qwen25_3b_java_clean673_coq_${RUN_ID}"
COQ_TRAIN_TASK="pretrain_qwen25_3b_java_clean673_coq_${DATA_STAMP}"
COQ_EVAL_TASK="qwen25_3b_mbjp_coq_eval_${DATA_STAMP}"
ARTIFACT_DIR="artifacts/major_revision_qwen25_3b_general_${RUN_ID}"
mkdir -p "$ARTIFACT_DIR"

case "$ACTION" in
  train_plain)
    CUDA_VISIBLE_DEVICES="$GPUS" "$ACCELERATE" launch \
      --num_processes "$PROCESSES" --main_process_port "$PORT" \
      --mixed_precision bf16 \
      baselines/java_baselines/run_qwen_plain_java.py train \
      --model "$MODEL" \
      --output_dir "$PLAIN_MODEL_DIR" \
      --metrics_file "$ARTIFACT_DIR/plain_train_metrics.jsonl" \
      --seed 19970316 \
      "$@"
    ;;
  train_coq)
    CUDA_VISIBLE_DEVICES="$GPUS" "$ACCELERATE" launch \
      --num_processes "$PROCESSES" --main_process_port "$PORT" \
      --mixed_precision bf16 \
      run.py --task "$COQ_TRAIN_TASK" \
      --model_output_task "$COQ_MODEL_TASK" \
      --runtime_dir "tmp/runtime_state/${COQ_MODEL_TASK}" \
      --metrics_file "$ARTIFACT_DIR/coq_train_metrics.jsonl" \
      --no_swanlab --distributed_timeout_minutes 180 \
      --max_epoch 19 --eval_step 5 --eval_step_init 5 \
      --batch_size 1 --lr 2e-5 \
      "$@"
    ;;
  eval_plain)
    if [ "$#" -lt 2 ]; then
      echo "eval_plain requires <checkpoint_dir> <output_tag>" >&2
      exit 2
    fi
    CHECKPOINT="$1"
    OUTPUT_TAG="$2"
    shift 2
    CUDA_VISIBLE_DEVICES="$GPUS" "$ACCELERATE" launch \
      --num_processes "$PROCESSES" --main_process_port "$PORT" \
      --mixed_precision bf16 \
      baselines/java_baselines/run_qwen_plain_java.py eval \
      --checkpoint "$CHECKPOINT" \
      --output_dir "Utils/output/mbjp_original_test_t5gemma2_20260731_test_ans/${OUTPUT_TAG}" \
      "$@"
    ;;
  eval_coq)
    if [ "$#" -lt 3 ]; then
      echo "eval_coq requires <train_time> <checkpoint_epoch> <output_tag>" >&2
      exit 2
    fi
    TRAIN_TIME="$1"
    CHECKPOINT_EPOCH="$2"
    OUTPUT_TAG="$3"
    shift 3
    CHECKPOINT_ARGS=(--model_type last)
    if [ "$CHECKPOINT_EPOCH" != "final" ]; then
      CHECKPOINT_ARGS=(--train_time "$TRAIN_TIME" --checkpoint_epoch "$CHECKPOINT_EPOCH")
    fi
    CUDA_VISIBLE_DEVICES="$GPUS" "$ACCELERATE" launch \
      --num_processes "$PROCESSES" --main_process_port "$PORT" \
      --mixed_precision bf16 \
      run.py --task "$COQ_EVAL_TASK" \
      --model_output_task "$COQ_MODEL_TASK" \
      --runtime_dir "tmp/runtime_state/${COQ_EVAL_TASK}_${CHECKPOINT_EPOCH}" \
      --eval --eval_split test "${CHECKPOINT_ARGS[@]}" --beam_size 10 \
      --length_penalty 0.1 --disable_coq_check --force_coq_decoder \
      --disable_tqdm --output_tag "$OUTPUT_TAG" \
      --no_swanlab --distributed_timeout_minutes 180 \
      "$@"
    ;;
  *)
    echo "unknown action: $ACTION" >&2
    exit 2
    ;;
esac
