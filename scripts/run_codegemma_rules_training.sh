#!/usr/bin/env bash
set -euo pipefail

# Full CodeGemma -> ProofT5 rule representation run.  This script deliberately
# writes only timestamped/newly named artifacts; it never reuses or overwrites
# the frozen ProofT5/Qwen results.
#
#   train_pretrain   five passes over the 9,856-row grammar pretraining set
#   train_java       thirty passes over the 673-row clean Java set
#   eval             ten grammar-constrained MBJP candidates per task

if [[ $# -lt 1 ]]; then
  echo "usage: $0 train_pretrain|train_java|eval [extra run.py args...]" >&2
  exit 2
fi

ACTION="$1"
shift
STAMP="${PROOFT5_CODEGEMMA_STAMP:-20260826_v3}"
PRETRAIN_OUTPUT="${PROOFT5_CODEGEMMA_PRETRAIN_OUTPUT:-codegemma2b_pretrain_rules_full5pass_${STAMP}}"
ACCELERATE="${PROOFT5_CODEGEMMA_ACCELERATE:-/data2/x/hzc/.uv-envs/prooft5-t5gemma-py313/bin/accelerate}"
PYTHON="${PROOFT5_CODEGEMMA_PYTHON:-/data2/x/hzc/.uv-envs/prooft5-t5gemma-py313/bin/python}"
GPUS="${PROOFT5_CODEGEMMA_GPUS:-0,1,2,4,5,6,7}"
PROCESSES="${PROOFT5_CODEGEMMA_PROCESSES:-7}"
PORT="${PROOFT5_CODEGEMMA_PORT:-29691}"
ARTIFACT="artifacts/major_revision_codegemma_rules_${STAMP}"

case "$ACTION" in
  train_pretrain)
    TASK="pretrain_codegemma2b_java_rules_${STAMP}"
    OUTPUT="codegemma2b_pretrain_rules_full5pass_${STAMP}"
    METRICS="$ARTIFACT/pretrain_metrics.jsonl"
    ;;
  train_java)
    TASK="codegemma2b_java_rules_673_${STAMP}"
    OUTPUT="codegemma2b_java_rules_full30pass_${STAMP}"
    METRICS="$ARTIFACT/java_metrics.jsonl"
    ;;
  eval)
    TASK="codegemma2b_mbjp_eval_noio_${STAMP}"
    OUTPUT="codegemma2b_java_rules_full30pass_${STAMP}"
    METRICS=""
    ;;
  *)
    echo "unknown action: $ACTION" >&2
    exit 2
    ;;
esac

mkdir -p "$ARTIFACT"
RUNTIME="tmp/runtime_state/${OUTPUT}"
TENSORBOARD="Utils/tensorboard/${TASK}/${OUTPUT}"
if [[ "$ACTION" != eval ]]; then
  if [[ -e "Utils/models/Model${OUTPUT}" || -e "$RUNTIME" || -e "$METRICS" ]]; then
    echo "refusing to overwrite existing run artifact for $OUTPUT" >&2
    exit 73
  fi
else
  if [[ ! -f "Utils/models/Model${OUTPUT}/last_model.ckpt" ]]; then
    echo "missing trained checkpoint: Utils/models/Model${OUTPUT}/last_model.ckpt" >&2
    exit 66
  fi
fi

COMMON=(
  --task "$TASK"
  --model_output_task "$OUTPUT"
  --runtime_dir "$RUNTIME"
  --no_swanlab
  --distributed_timeout_minutes 720
  --train_num_workers 0
  --eval_num_workers 0
)
if [[ "$ACTION" != eval ]]; then
  COMMON+=(--metrics_file "$METRICS" --tensorboard_dir "$TENSORBOARD")
  if [[ "$ACTION" == train_java ]]; then
    # The data task records the logical pretraining source; run.py loads the
    # actual checkpoint under the explicitly named model-output task.
    COMMON+=(--pretrain_name "$PRETRAIN_OUTPUT")
  fi
else
  COMMON+=(
    --eval
    --eval_split test
    --model_type last
    --beam_size 10
    --length_penalty 0.1
    --disable_tqdm
    --resume_output
    --output_tag "formal_codegemma_rules_${STAMP}"
    --disable_coq_check
  )
fi

CUDA_VISIBLE_DEVICES="$GPUS" \
  OMP_NUM_THREADS=8 MKL_NUM_THREADS=8 OPENBLAS_NUM_THREADS=8 NUMEXPR_NUM_THREADS=8 \
  TOKENIZERS_PARALLELISM=false \
  "$ACCELERATE" launch \
    --num_processes "$PROCESSES" \
    --main_process_port "$PORT" \
    --mixed_precision bf16 \
    run.py "${COMMON[@]}" "$@"
