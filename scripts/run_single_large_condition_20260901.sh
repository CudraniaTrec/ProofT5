#!/usr/bin/env bash
# Run one condition from the larger-model matrix.  This permits independent
# conditions to use otherwise idle GPUs while retaining the same protocol as
# run_large_decoder_matrix_20260901.sh.
set -u -o pipefail
if [ "$#" -lt 6 ]; then
  echo "usage: $0 MODEL_PATH SLUG GPU MODEL_TYPE COMPLETION_MODE CONDITION" >&2
  exit 2
fi
MODEL=$1; SLUG=$2; GPU=$3; MODEL_TYPE=$4; MODE=$5; CONDITION=$6
REPO=/data2/x/hzc/prooft5
ART=$REPO/artifacts/major_revision_decoder_only_multibenchmark_20260828
PY=/data2/x/hzc/.uv-envs/prooft5-t5gemma-py313/bin/python
export CUDA_VISIBLE_DEVICES="$GPU"

RUN_MODE=$MODE
case "$MODE" in
  full_source) NO_CHAT_ARG=() ;;
  full_source_plain) NO_CHAT_ARG=(--no_chat_template); RUN_MODE=full_source ;;
  prefix_completion) NO_CHAT_ARG=(--no_chat_template) ;;
  *) echo "unsupported completion mode: $MODE" >&2; exit 2 ;;
esac

case "$CONDITION" in
  mbjp_zero|mbjp_f3)
    DATA=artifacts/major_revision_decoder_only_noio_20260826/inputs/java_mbjp_original_test_noio.json
    TASK=mbjp_original_test_t5gemma2_20260731
    EXTRA=()
    [[ "$CONDITION" == *_f3 ]] && EXTRA=(--few_shot_k 3 --few_shot_style synthetic_minimal)
    ;;
  he_zero|he_f3)
    DATA=artifacts/major_revision_decoder_only_multibenchmark_20260827/inputs/humaneval_v15_test_noio.json
    TASK=java_humaneval_mbjp_native_semanticsupport_split90_10_t5gemma2_20260822_v15
    EXTRA=()
    [[ "$CONDITION" == *_f3 ]] && EXTRA=(--few_shot_k 3 --few_shot_style synthetic_minimal)
    ;;
  gfg_zero|gfg_f3)
    DATA=artifacts/major_revision_decoder_only_multibenchmark_20260827/inputs/gfg_v13_test_noio.json
    TASK=java_transcoder_gfg_mbjp_native_prompt_split80_20_t5gemma2_20260819_v13
    EXTRA=()
    [[ "$CONDITION" == *_f3 ]] && EXTRA=(--few_shot_k 3 --few_shot_style synthetic_minimal)
    ;;
  sufu_zero|sufu_f3)
    DATA=t5_llm/data/sufu_original_test_t5.json
    TASK=sufu_original_test_t5gemma2_20260731
    EXTRA=(--prompt_mode full_source --guidance_profile high_information)
    if [[ "$CONDITION" == *_f3 ]]; then
      EXTRA+=(--few_shot_k 3 --few_shot_dataset "$ART/inputs/sufu_few_shot_train_only_noio_notest_20260902.json" \
        --few_shot_ids incre-tests-synduce-constraints-sortedlist-parallel_max2,incre-tests-synduce-zipper-list_sum,incre-tests-synduce-constraints-all_positive-sndmax)
    fi
    ;;
  *) echo "unknown condition: $CONDITION" >&2; exit 2 ;;
esac

TAG="${SLUG}_${CONDITION}_20260901"
LOG="$ART/${TAG}_single.log"
if [[ "$CONDITION" == sufu_* ]]; then
  "$PY" "$REPO/baselines/java_baselines/run_decoder_only_sufu.py" \
    --backend hf --model "$MODEL" --model_family causal --dtype bf16 --device cuda \
    --local_files_only --candidates 1 --greedy_first --max_tokens 1024 \
    --temperature 0.8 --top_p 0.95 --seed 273567 "${NO_CHAT_ARG[@]}" "${EXTRA[@]}" \
    --dataset_json "$DATA" --score_task "$TASK" --score_split test \
    --output_tag "$TAG" --resume >"$LOG" 2>&1
else
  "$PY" "$REPO/baselines/java_baselines/run_decoder_only_zero_few_shot.py" \
    --backend hf --model "$MODEL" --model_family causal --dtype bf16 --device cuda \
    --local_files_only --candidates 1 --greedy_first --max_tokens 1024 \
    --temperature 0.8 --top_p 0.95 --seed 273567 \
    --completion_mode "$RUN_MODE" --stop_at_java_class --reject_io_examples \
    "${NO_CHAT_ARG[@]}" --dataset_json "$DATA" --dataset_split test \
    --score_task "$TASK" --score_split test --output_tag "$TAG" --resume \
    "${EXTRA[@]}" >"$LOG" 2>&1
fi
rc=$?
if [ "$rc" -ne 0 ]; then echo "GENERATION_FAILED $TAG rc=$rc" | tee -a "$LOG"; exit "$rc"; fi
if [[ "$CONDITION" == sufu_* ]]; then
  "$PY" "$REPO/score_sufu_no_write.py" --task "$TASK" --split test --output_tag "$TAG" \
    --pass_at_k 1 --model_output_task "$TAG" --model_type "$MODEL_TYPE" \
    --json_out "$ART/${TAG}_score.json" >>"$LOG" 2>&1
else
  "$PY" "$REPO/score_java_no_write.py" --task "$TASK" --split test --output_tag "$TAG" \
    --pass_at_k 1 --timeout 10 --model_output_task "$TAG" --model_type "$MODEL_TYPE" \
    --json_out "$ART/${TAG}_score.json" >>"$LOG" 2>&1
fi
echo "CONDITION_COMPLETE $TAG rc=$?" | tee -a "$LOG"
