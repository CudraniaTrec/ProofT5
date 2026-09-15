#!/usr/bin/env bash
# RQ3 realignment stage 1: ordinary control + Repilot(supportfix) on the
# Table-1 clean673 baseline checkpoint (beam-10 row owner), frozen sampling
# protocol unchanged (temp 0.8, top_p 0.95, top_k 50, greedy_first, seed 273567).
set -euo pipefail
cd /data2/x/hzc/prooft5

export PROOFT5_MBJP_BASELINE_MODEL="t5_llm/models/t5gemma2-2b_java_clean673_noleak_b5_lr5em5_pass30_20260811_after_clean_coqview/20260811_after_clean_coqview/epoch_20"

run_pair() {
  local gpu="$1"
  local indices="$2"
  local shard="$3"
  local ordinary_tag="rq3clean_mbjp_ordinary_matched_b10_s${shard}_20260914"
  local repilot_tag="rq3clean_mbjp_repilot_supportfix_b10_s${shard}_20260914"
  PROOFT5_BASELINE_GPU="$gpu" \
    baselines/java_baselines/run_frozen_t5gemma_baseline.sh \
    ordinary mbjp "$ordinary_tag" --indices "$indices" \
    >"tmp/${ordinary_tag}.log" 2>&1
  PROOFT5_BASELINE_GPU="$gpu" \
    baselines/java_baselines/run_frozen_t5gemma_baseline.sh \
    repilot mbjp "$repilot_tag" --indices "$indices" \
    >"tmp/${repilot_tag}.log" 2>&1
}

run_pair 0 "0,1,2,3,4,5,6,7,8,9,10,11" 0 & pid_0=$!
run_pair 1 "12,13,14,15,16,17,18,19,20,21,22" 1 & pid_1=$!
run_pair 2 "23,24,25,26,27,28,29,30,31,32,33" 2 & pid_2=$!
run_pair 3 "34,35,36,37,38,39,40,41,42,43,44" 3 & pid_3=$!
run_pair 4 "45,46,47,48,49,50,51,52,53,54,55" 4 & pid_4=$!
run_pair 5 "56,57,58,59,60,61,62,63,64,65,66" 5 & pid_5=$!

wait "$pid_0"
wait "$pid_1"
wait "$pid_2"
wait "$pid_3"
wait "$pid_4"
wait "$pid_5"
echo "stage1 done"
