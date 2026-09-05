#!/usr/bin/env bash
# Re-run the SuFu zero/three-shot pass@1 controls after the explicit
# completion-boundary and train-only few-shot fixes.  This script is additive:
# it uses new output tags and never overwrites earlier result directories.
set -u -o pipefail

if [ "$#" -lt 5 ]; then
  echo "usage: $0 MODEL_PATH SLUG GPU MODEL_TYPE CHAT_MODE [MAX_TOKENS]" >&2
  echo "  CHAT_MODE: native (use tokenizer chat template) or plain" >&2
  exit 2
fi

MODEL=$1
SLUG=$2
GPU=$3
MODEL_TYPE=$4
CHAT_MODE=$5
MAX_TOKENS=${6:-2048}

ROOT=/data2/x/hzc/prooft5
PY=/data2/x/hzc/.uv-envs/prooft5-t5gemma-py313/bin/python
ART=$ROOT/artifacts/major_revision_decoder_only_multibenchmark_20260828
DATA=$ROOT/t5_llm/data/sufu_original_test_t5.json
TASK=sufu_original_test_t5gemma2_20260731
FS=$ART/inputs/sufu_few_shot_train_only_noio_notest_20260902.json
IDS=incre-tests-synduce-constraints-sortedlist-parallel_max2,incre-tests-synduce-zipper-list_sum,incre-tests-synduce-constraints-all_positive-sndmax

if [ "$CHAT_MODE" = native ]; then
  CHAT_ARG=()
elif [ "$CHAT_MODE" = plain ]; then
  CHAT_ARG=(--no_chat_template)
else
  echo "unsupported CHAT_MODE=$CHAT_MODE" >&2
  exit 2
fi

export CUDA_VISIBLE_DEVICES=$GPU

run_one() {
  local condition=$1
  local tag=${SLUG}_sufu_${condition}_trainonly_valid_stopmain_20260902
  local log=$ART/${tag}.log
  local extra=()
  if [ "$condition" = f3 ]; then
    extra=(--few_shot_k 3 --few_shot_dataset "$FS" --few_shot_ids "$IDS")
  fi
  "$PY" "$ROOT/baselines/java_baselines/run_decoder_only_sufu.py" \
    --backend hf --model "$MODEL" --model_family causal --dtype bf16 --device cuda \
    --local_files_only --candidates 1 --greedy_first --max_tokens "$MAX_TOKENS" \
    --temperature 0.8 --top_p 0.95 --seed 273567 "${CHAT_ARG[@]}" "${extra[@]}" \
    --prompt_mode full_source --guidance_profile high_information \
    --dataset_json "$DATA" --score_task "$TASK" --score_split test \
    --output_tag "$tag" --resume >"$log" 2>&1
  local gen_rc=$?
  if [ "$gen_rc" -ne 0 ]; then
    echo "GENERATION_FAILED $tag rc=$gen_rc" | tee -a "$log"
    return "$gen_rc"
  fi
  "$PY" "$ROOT/score_sufu_no_write.py" --task "$TASK" --split test \
    --output_tag "$tag" --pass_at_k 1 --model_output_task "$tag" \
    --model_type "$MODEL_TYPE" --json_out "$ART/${tag}_score.json" \
    >>"$log" 2>&1
  local score_rc=$?
  echo "CONDITION_COMPLETE $tag rc=$score_rc" | tee -a "$log"
  return "$score_rc"
}

run_one zero || exit $?
run_one f3 || exit $?
