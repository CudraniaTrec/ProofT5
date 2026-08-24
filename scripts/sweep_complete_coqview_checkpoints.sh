#!/usr/bin/env bash
# Generate and functionally score every saved checkpoint of one final CoqView run.
#
# Usage:
#   scripts/sweep_complete_coqview_checkpoints.sh TASK MODEL_OUTPUT_TASK java|sufu

set -euo pipefail

if [ "$#" -ne 3 ]; then
  printf 'usage: %s TASK MODEL_OUTPUT_TASK java|sufu\n' "$0" >&2
  exit 64
fi

SWEEP_TASK="$1"
SWEEP_MODEL="$2"
SWEEP_BRANCH="$3"
case "$SWEEP_BRANCH" in java|sufu) ;; *) printf 'branch must be java or sufu\n' >&2; exit 64 ;; esac

cd /data2/x/hzc/prooft5
SWEEP_PY="/data2/x/hzc/.uv-envs/prooft5-t5gemma-py313/bin/python"
SWEEP_ACC="/data2/x/hzc/.uv-envs/prooft5-t5gemma-py313/bin/accelerate"
SWEEP_GPUS="${COQVIEW_SWEEP_GPUS:-0,1,2,3,4,5,6,7}"
IFS=',' read -r -a SWEEP_GPU_ARRAY <<< "$SWEEP_GPUS"
SWEEP_NUM_PROCESSES="${COQVIEW_SWEEP_NUM_PROCESSES:-${#SWEEP_GPU_ARRAY[@]}}"
SWEEP_PORT="${COQVIEW_SWEEP_PORT:-29683}"
SWEEP_SCORE_TIMEOUTS="${COQVIEW_SCORE_TIMEOUTS:-1,10}"
SWEEP_CANDIDATE_MULTIPLIER="${COQVIEW_CANDIDATE_MULTIPLIER:-20}"
SWEEP_KINDS="${COQVIEW_SWEEP_KINDS:-all}"
SWEEP_LABEL="${COQVIEW_SWEEP_LABEL:-20260801}"
SWEEP_LENGTH_PENALTIES="${COQVIEW_SWEEP_LENGTH_PENALTIES:-0,0.1}"
SWEEP_EVAL_INDICES="${COQVIEW_EVAL_INDICES:-}"
SWEEP_ROOT="Utils/models/Model${SWEEP_MODEL}"

if ! [[ "$SWEEP_LABEL" =~ ^[A-Za-z0-9._-]+$ ]]; then
  printf 'COQVIEW_SWEEP_LABEL must be a filename-safe label\n' >&2
  exit 64
fi
if ! [[ "$SWEEP_CANDIDATE_MULTIPLIER" =~ ^[1-9][0-9]*$ ]]; then
  printf 'COQVIEW_CANDIDATE_MULTIPLIER must be a positive integer\n' >&2
  exit 64
fi
if ! [[ "$SWEEP_NUM_PROCESSES" =~ ^[1-9][0-9]*$ ]]; then
  printf 'COQVIEW_SWEEP_NUM_PROCESSES must be a positive integer\n' >&2
  exit 64
fi

if [ ! -d "$SWEEP_ROOT" ]; then
  printf 'model output directory is absent: %s\n' "$SWEEP_ROOT" >&2
  exit 66
fi
if [ ! -f "Utils/data/${SWEEP_TASK}/coqview_build_manifest.json" ]; then
  printf 'not an audited complete CoqView task: %s\n' "$SWEEP_TASK" >&2
  exit 66
fi

mapfile -t SWEEP_RUN_DIRS < <(find "$SWEEP_ROOT" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort)
if [ "${#SWEEP_RUN_DIRS[@]}" -ne 1 ]; then
  printf 'expected exactly one timestamped run directory under %s, got %s\n' "$SWEEP_ROOT" "${#SWEEP_RUN_DIRS[@]}" >&2
  exit 65
fi
SWEEP_RUN_DIR="${SWEEP_RUN_DIRS[0]}"

score_one() {
  local kind="$1"
  local checkpoint_path="$2"
  local length_penalty="$3"
  if ! [[ "$length_penalty" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
    printf 'invalid non-negative length penalty: %s\n' "$length_penalty" >&2
    exit 64
  fi
  local penalty_tag="${length_penalty//./p}"
  local output_tag="papercheck_${SWEEP_MODEL}_${kind}_b10_lp${penalty_tag}_${SWEEP_LABEL}"
  local eval_args=()
  local score_scope_args=()
  local audit_scope_args=()
  local score_checkpoint_args=(--model_type "$kind")
  local eval_runtime_args=(--coq_candidate_multiplier "$SWEEP_CANDIDATE_MULTIPLIER")
  if [ "$kind" = "final" ]; then
    eval_args+=(--model_type last)
  else
    local epoch="${kind#epoch}"
    eval_args+=(--train_time "$SWEEP_RUN_DIR" --checkpoint_epoch "$epoch")
    score_checkpoint_args+=(--train_time "$SWEEP_RUN_DIR" --checkpoint_epoch "$epoch")
  fi
  if [ -n "$SWEEP_EVAL_INDICES" ]; then
    eval_args+=(--eval_indices "$SWEEP_EVAL_INDICES")
    score_scope_args+=(--indices "$SWEEP_EVAL_INDICES")
    audit_scope_args+=(--indices "$SWEEP_EVAL_INDICES")
  fi
  if [ -e "Utils/output/${SWEEP_TASK}_test_ans/${output_tag}" ]; then
    printf 'refusing to overwrite evaluation artifact for %s\n' "$kind" >&2
    exit 73
  fi
  if [ "$SWEEP_BRANCH" = "sufu" ] && [ -e "tmp/${output_tag}_surface_audit.json" ]; then
    printf 'refusing to overwrite surface-audit artifact for %s\n' "$kind" >&2
    exit 73
  fi
  for score_timeout in "${SWEEP_SCORE_TIMEOUT_ARRAY[@]}"; do
    if [ -e "tmp/${output_tag}_score_timeout${score_timeout}.json" ]; then
      printf 'refusing to overwrite score artifact for %s timeout %s\n' \
        "$kind" "$score_timeout" >&2
      exit 73
    fi
  done
  if [ ! -f "$checkpoint_path" ]; then
    printf 'checkpoint absent: %s\n' "$checkpoint_path" >&2
    exit 66
  fi
  local checkpoint_sha
  checkpoint_sha="$(sha256sum "$checkpoint_path" | awk '{print $1}')"
  printf '[%s] evaluating %s (%s)\n' "$(date -Iseconds)" "$kind" "$checkpoint_sha"

  if [ "$SWEEP_BRANCH" = "java" ]; then
    eval_runtime_args+=(--coq_workers 8 --coq_timeout 20)
  else
    # Do not rely on task-name heuristics for the paper-facing SuFu run.  The
    # exact returned surface program must pass the strict type guard.
    eval_runtime_args+=(--force_sufu_type_check)
  fi

  CUDA_VISIBLE_DEVICES="$SWEEP_GPUS" \
  OMP_NUM_THREADS=8 MKL_NUM_THREADS=8 OPENBLAS_NUM_THREADS=8 NUMEXPR_NUM_THREADS=8 \
  TOKENIZERS_PARALLELISM=false \
  PROOFT5_DISTRIBUTED_TIMEOUT_MINUTES=720 \
  TORCH_NCCL_HEARTBEAT_TIMEOUT_SEC=7200 \
  TORCH_NCCL_ASYNC_ERROR_HANDLING=1 \
  PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
  "$SWEEP_ACC" launch --config_file tmp/acc_config_ddp_bf16.yaml \
    --num_processes "$SWEEP_NUM_PROCESSES" \
    --main_process_port "$SWEEP_PORT" run.py \
    --eval --task "$SWEEP_TASK" --model_output_task "$SWEEP_MODEL" \
    --eval_split test --output_tag "$output_tag" --beam_size 10 \
    --length_penalty "$length_penalty" \
    --runtime_dir "tmp/runtime_state/${output_tag}" \
    --batch_size_eval 1 --eval_num_workers 0 --disable_tqdm --no_swanlab \
    "${eval_runtime_args[@]}" \
    "${eval_args[@]}"

  if [ "$SWEEP_BRANCH" = "sufu" ]; then
    "$SWEEP_PY" scripts/audit_sufu_generated_candidates.py \
      --task "$SWEEP_TASK" --split test --output_tag "$output_tag" \
      --beam_size 10 --require_beam_metadata \
      "${audit_scope_args[@]}" \
      --json_out "tmp/${output_tag}_surface_audit.json"
  fi

  for score_timeout in "${SWEEP_SCORE_TIMEOUT_ARRAY[@]}"; do
    local score_json="tmp/${output_tag}_score_timeout${score_timeout}.json"
    if [ "$SWEEP_BRANCH" = "java" ]; then
      "$SWEEP_PY" score_java_no_write.py --task "$SWEEP_TASK" --split test \
        --output_tag "$output_tag" --pass_at_k 10 --workers 64 --timeout "$score_timeout" \
        --model_output_task "$SWEEP_MODEL" "${score_checkpoint_args[@]}" \
        "${score_scope_args[@]}" \
        --model_checkpoint_path "$checkpoint_path" --model_checkpoint_sha256 "$checkpoint_sha" \
        --json_out "$score_json"
    else
      "$SWEEP_PY" score_sufu_no_write.py --task "$SWEEP_TASK" --split test \
        --output_tag "$output_tag" --pass_at_k 10 --workers 32 --timeout "$score_timeout" \
        --model_output_task "$SWEEP_MODEL" "${score_checkpoint_args[@]}" \
        "${score_scope_args[@]}" \
        --model_checkpoint_path "$checkpoint_path" --model_checkpoint_sha256 "$checkpoint_sha" \
        --json_out "$score_json"
    fi
  done
}

IFS=',' read -r -a SWEEP_PENALTY_ARRAY <<< "$SWEEP_LENGTH_PENALTIES"
if [ "${#SWEEP_PENALTY_ARRAY[@]}" -eq 0 ]; then
  printf 'COQVIEW_SWEEP_LENGTH_PENALTIES must not be empty\n' >&2
  exit 64
fi
IFS=',' read -r -a SWEEP_SCORE_TIMEOUT_ARRAY <<< "$SWEEP_SCORE_TIMEOUTS"
if [ "${#SWEEP_SCORE_TIMEOUT_ARRAY[@]}" -eq 0 ]; then
  printf 'COQVIEW_SCORE_TIMEOUTS must not be empty\n' >&2
  exit 64
fi
for score_timeout in "${SWEEP_SCORE_TIMEOUT_ARRAY[@]}"; do
  if ! [[ "$score_timeout" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
    printf 'invalid non-negative scoring timeout: %s\n' "$score_timeout" >&2
    exit 64
  fi
done

should_score() {
  local kind="$1"
  [ "$SWEEP_KINDS" = "all" ] && return 0
  case ",${SWEEP_KINDS}," in
    *",${kind},"*) return 0 ;;
    *) return 1 ;;
  esac
}

for checkpoint in "$SWEEP_ROOT/$SWEEP_RUN_DIR"/epoch*_model.ckpt; do
  [ -e "$checkpoint" ] || continue
  checkpoint_name="$(basename "$checkpoint" _model.ckpt)"
  if should_score "$checkpoint_name"; then
    for length_penalty in "${SWEEP_PENALTY_ARRAY[@]}"; do
      score_one "$checkpoint_name" "$checkpoint" "$length_penalty"
    done
  fi
done
if should_score final; then
  for length_penalty in "${SWEEP_PENALTY_ARRAY[@]}"; do
    score_one final "$SWEEP_ROOT/last_model.ckpt" "$length_penalty"
  done
fi
