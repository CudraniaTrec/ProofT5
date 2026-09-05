#!/usr/bin/env bash
# Run a complete four-benchmark, zero/three-shot matrix for one locally
# available larger decoder-only checkpoint.  This script is additive: every
# output tag is new and --resume only fills missing candidate files.
set -u -o pipefail

cd /data2/x/hzc/prooft5 || exit 1

if [ "$#" -lt 3 ]; then
  echo "usage: $0 MODEL_PATH MODEL_SLUG GPU [MODEL_TYPE] [COMPLETION_MODE]" >&2
  exit 2
fi

MODEL=$1
SLUG=$2
GPU=$3
MODEL_TYPE=${4:-qwen3.6}
COMPLETION_MODE=${5:-full_source}

RUN_COMPLETION_MODE=$COMPLETION_MODE
case "$COMPLETION_MODE" in
  full_source|prefix_completion) ;;
  full_source_plain)
    # Post-trained checkpoints can still be evaluated with the matched plain
    # tokenizer stream required by the large-candidate protocol.
    RUN_COMPLETION_MODE=full_source
    ;;
  *) echo "unsupported COMPLETION_MODE=$COMPLETION_MODE" >&2; exit 2 ;;
esac

NO_CHAT_ARG=()
if [ "$COMPLETION_MODE" != "full_source" ]; then
  # Base checkpoints are evaluated as plain code-continuation models.  Do not
  # inject a tokenizer chat template into their prompt stream.
  NO_CHAT_ARG+=(--no_chat_template)
fi

export CUDA_VISIBLE_DEVICES="$GPU"
PY=/data2/x/hzc/.uv-envs/prooft5-t5gemma-py313/bin/python
ART=artifacts/major_revision_decoder_only_multibenchmark_20260828
LOG="$ART/${SLUG}_driver_20260901.log"

MBJP_DATA=artifacts/major_revision_decoder_only_noio_20260826/inputs/java_mbjp_original_test_noio.json
MBJP_TASK=mbjp_original_test_t5gemma2_20260731
HE_DATA=artifacts/major_revision_decoder_only_multibenchmark_20260827/inputs/humaneval_v15_test_noio.json
HE_TASK=java_humaneval_mbjp_native_semanticsupport_split90_10_t5gemma2_20260822_v15
GFG_DATA=artifacts/major_revision_decoder_only_multibenchmark_20260827/inputs/gfg_v13_test_noio.json
GFG_TASK=java_transcoder_gfg_mbjp_native_prompt_split80_20_t5gemma2_20260819_v13
SUFU_DATA=t5_llm/data/sufu_original_test_t5.json
SUFU_TASK=sufu_original_test_t5gemma2_20260731
SUFU_FEWSHOT="$ART/inputs/sufu_few_shot_train_only_noio_notest_20260902.json"
SUFU_IDS=incre-tests-synduce-constraints-sortedlist-parallel_max2,incre-tests-synduce-zipper-list_sum,incre-tests-synduce-constraints-all_positive-sndmax

log() { echo "[$(date -u +%H:%M:%S)] $*" | tee -a "$LOG"; }

run_java() {
  local dataset=$1 task=$2 tag=$3 name=$4; shift 4
  log "START java $name tag=$tag"
  "$PY" baselines/java_baselines/run_decoder_only_zero_few_shot.py \
    --backend hf --model "$MODEL" --model_family causal --dtype bf16 --device cuda \
    --local_files_only --candidates 1 --greedy_first --max_tokens 1024 \
    --temperature 0.8 --top_p 0.95 --seed 273567 \
    --completion_mode "$RUN_COMPLETION_MODE" --stop_at_java_class --reject_io_examples \
    "${NO_CHAT_ARG[@]}" \
    --dataset_json "$dataset" --dataset_split test --score_task "$task" \
    --score_split test --output_tag "$tag" --resume "$@" \
    > "$ART/${name}_20260901.log" 2>&1
  local gen_rc=$?
  log "END java $name generation rc=$gen_rc"
  if [ "$gen_rc" -ne 0 ]; then return "$gen_rc"; fi
  "$PY" score_java_no_write.py --task "$task" --split test --output_tag "$tag" \
    --pass_at_k 1 --timeout 10 --model_output_task "$tag" --model_type "$MODEL_TYPE" \
    --json_out "$ART/${name}_score.json" \
    >> "$ART/${name}_20260901.log" 2>&1
  local score_rc=$?
  log "SCORE java $name rc=$score_rc"
  return "$score_rc"
}

run_sufu() {
  local tag=$1 name=$2; shift 2
  log "START sufu $name tag=$tag"
  "$PY" baselines/java_baselines/run_decoder_only_sufu.py \
    --backend hf --model "$MODEL" --model_family causal --dtype bf16 --device cuda \
    --local_files_only --candidates 1 --greedy_first --max_tokens 1024 \
    --temperature 0.8 --top_p 0.95 --seed 273567 \
    "${NO_CHAT_ARG[@]}" \
    --prompt_mode full_source --guidance_profile high_information \
    --dataset_json "$SUFU_DATA" --score_task "$SUFU_TASK" --score_split test \
    --output_tag "$tag" --resume "$@" \
    > "$ART/${name}_20260901.log" 2>&1
  local gen_rc=$?
  log "END sufu $name generation rc=$gen_rc"
  if [ "$gen_rc" -ne 0 ]; then return "$gen_rc"; fi
  "$PY" score_sufu_no_write.py --task "$SUFU_TASK" --split test --output_tag "$tag" \
    --pass_at_k 1 --model_output_task "$tag" --model_type "$MODEL_TYPE" \
    --json_out "$ART/${name}_score.json" \
    >> "$ART/${name}_20260901.log" 2>&1
  local score_rc=$?
  log "SCORE sufu $name rc=$score_rc"
  return "$score_rc"
}

run_java "$MBJP_DATA" "$MBJP_TASK" "${SLUG}_mbjp_zero_20260901" "${SLUG}_mbjp_zero"
run_java "$MBJP_DATA" "$MBJP_TASK" "${SLUG}_mbjp_f3_20260901" "${SLUG}_mbjp_f3" \
  --few_shot_k 3 --few_shot_style synthetic_minimal
run_java "$HE_DATA" "$HE_TASK" "${SLUG}_he_zero_20260901" "${SLUG}_he_zero"
run_java "$HE_DATA" "$HE_TASK" "${SLUG}_he_f3_20260901" "${SLUG}_he_f3" \
  --few_shot_k 3 --few_shot_style synthetic_minimal
run_java "$GFG_DATA" "$GFG_TASK" "${SLUG}_gfg_zero_20260901" "${SLUG}_gfg_zero"
run_java "$GFG_DATA" "$GFG_TASK" "${SLUG}_gfg_f3_20260901" "${SLUG}_gfg_f3" \
  --few_shot_k 3 --few_shot_style synthetic_minimal
run_sufu "${SLUG}_sufu_zero_20260901" "${SLUG}_sufu_zero"
run_sufu "${SLUG}_sufu_f3_20260901" "${SLUG}_sufu_f3" \
  --few_shot_k 3 --few_shot_dataset "$SUFU_FEWSHOT" --few_shot_ids "$SUFU_IDS"

log "DRIVER COMPLETE slug=$SLUG"
