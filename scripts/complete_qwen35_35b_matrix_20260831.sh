#!/bin/bash
# Complete the Qwen3.5-35B-A3B four-benchmark matrix (2026-08-31).
# Six conditions (MBJP/GFG/SuFu x zero/F3) died right after weight loading on
# 2026-08-28; their output directories are empty and are filled with --resume.
# HumanEval zero/F3 candidates were already complete and are scored first.
# Runs are serial on one GPU; each generation is followed immediately by its
# scorer so a score JSON exists only when its candidate set is complete.
cd /data2/x/hzc/prooft5 || exit 1
export CUDA_VISIBLE_DEVICES="${QWEN35_35B_GPU:-7}"
PY=/data2/x/hzc/.uv-envs/prooft5-t5gemma-py313/bin/python
MODEL=/data2/x/hzc/models/qwen/Qwen3.5-35B-A3B
ART=artifacts/major_revision_decoder_only_multibenchmark_20260828
RUNLOG="$ART/qwen35_35b_driver_20260831.log"

log() { echo "[$(date -u +%H:%M:%S)] $*" | tee -a "$RUNLOG"; }

run_java() { # dataset score_task tag name extra...
  local dataset=$1 task=$2 tag=$3 name=$4; shift 4
  log "START java $name ($tag)"
  "$PY" baselines/java_baselines/run_decoder_only_zero_few_shot.py \
    --backend hf --model "$MODEL" --model_family causal --dtype bf16 --device cuda \
    --local_files_only --candidates 1 --greedy_first --max_tokens 1024 \
    --temperature 0.8 --top_p 0.95 --seed 273567 \
    --completion_mode full_source --stop_at_java_class --reject_io_examples \
    --dataset_json "$dataset" --score_task "$task" --output_tag "$tag" --resume \
    "$@" > "$ART/${name}_20260831.log" 2>&1
  local gen_rc=$?
  log "END   java $name generation rc=$gen_rc"
  if [ "$gen_rc" -ne 0 ]; then return "$gen_rc"; fi
  "$PY" score_java_no_write.py --task "$task" --split test --output_tag "$tag" \
    --pass_at_k 1 --timeout 10 --model_output_task "$tag" --model_type "qwen3.5-35b" \
    --json_out "$ART/${name}_score.json" >> "$ART/${name}_20260831.log" 2>&1
  log "SCORE java $name rc=$?"
}

run_sufu() { # tag name extra...
  local tag=$1 name=$2; shift 2
  log "START sufu $name ($tag)"
  "$PY" baselines/java_baselines/run_decoder_only_sufu.py \
    --backend hf --model "$MODEL" --model_family causal --dtype bf16 --device cuda \
    --local_files_only --candidates 1 --greedy_first --max_tokens 1024 \
    --temperature 0.8 --top_p 0.95 --seed 273567 \
    --prompt_mode full_source --guidance_profile high_information \
    --dataset_json t5_llm/data/sufu_original_test_t5.json \
    --score_task sufu_original_test_t5gemma2_20260731 --output_tag "$tag" --resume \
    "$@" > "$ART/${name}_20260831.log" 2>&1
  local gen_rc=$?
  log "END   sufu $name generation rc=$gen_rc"
  if [ "$gen_rc" -ne 0 ]; then return "$gen_rc"; fi
  "$PY" score_sufu_no_write.py --task sufu_original_test_t5gemma2_20260731 \
    --split test --output_tag "$tag" --pass_at_k 1 --model_output_task "$tag" \
    --model_type "qwen3.5-35b" \
    --json_out "$ART/${name}_score.json" >> "$ART/${name}_20260831.log" 2>&1
  log "SCORE sufu $name rc=$?"
}

MBJP_DATA=artifacts/major_revision_decoder_only_noio_20260826/inputs/java_mbjp_original_test_noio.json
GFG_DATA=artifacts/major_revision_decoder_only_multibenchmark_20260827/inputs/gfg_v13_test_noio.json
GFG_TASK=java_transcoder_gfg_mbjp_native_prompt_split80_20_t5gemma2_20260819_v13

run_java "$MBJP_DATA" mbjp_original_test_t5gemma2_20260731 \
  qwen35_35b_mbjp_zero_full_20260828 qwen35_35b_mbjp_zero
run_java "$MBJP_DATA" mbjp_original_test_t5gemma2_20260731 \
  qwen35_35b_mbjp_f3_full_20260828 qwen35_35b_mbjp_f3 \
  --few_shot_k 3 --few_shot_style synthetic_minimal
run_sufu qwen35_35b_sufu_zero_highinfo_20260828 qwen35_35b_sufu_zero
run_sufu qwen35_35b_sufu_f3_highinfo_20260828 qwen35_35b_sufu_f3 \
  --few_shot_k 3 \
  --few_shot_dataset "$ART/inputs/sufu_few_shot_train_only_noio_notest_20260902.json" \
  --few_shot_ids incre-tests-synduce-constraints-sortedlist-parallel_max2,incre-tests-synduce-zipper-list_sum,incre-tests-synduce-constraints-all_positive-sndmax
run_java "$GFG_DATA" "$GFG_TASK" \
  qwen35_35b_gfg_zero_full_20260828 qwen35_35b_gfg_zero
run_java "$GFG_DATA" "$GFG_TASK" \
  qwen35_35b_gfg_f3_full_20260828 qwen35_35b_gfg_f3 \
  --few_shot_k 3 --few_shot_style synthetic_minimal

log "DRIVER COMPLETE"
