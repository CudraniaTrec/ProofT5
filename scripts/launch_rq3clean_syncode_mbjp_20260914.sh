#!/usr/bin/env bash
# RQ3 realignment stage 2: SynCode (upstream javafix protocol) on the clean673
# checkpoint, sharded by candidate ranks exactly like the frozen 2026-08-25 run.
set -euo pipefail
cd /data2/x/hzc/prooft5

export PROOFT5_MBJP_BASELINE_MODEL="t5_llm/models/t5gemma2-2b_java_clean673_noleak_b5_lr5em5_pass30_20260811_after_clean_coqview/20260811_after_clean_coqview/epoch_20"

run_shard() {
  local gpu="$1"
  local ranks="$2"
  local tag="rq3clean_mbjp_syncode_javafix_b10_r${ranks/,/}_20260914"
  PROOFT5_BASELINE_GPU="$gpu" \
    baselines/java_baselines/run_frozen_t5gemma_baseline.sh \
    syncode mbjp "$tag" --candidate_ranks "$ranks" --resume >"tmp/${tag}.log" 2>&1
}

run_shard 0 "0,6" & pid_0=$!
run_shard 1 "1,7" & pid_1=$!
run_shard 2 "2,8" & pid_2=$!
run_shard 3 "3,9" & pid_3=$!
run_shard 4 "4"    & pid_4=$!
run_shard 5 "5"    & pid_5=$!

wait "$pid_0"; wait "$pid_1"; wait "$pid_2"; wait "$pid_3"; wait "$pid_4"; wait "$pid_5"
echo "stage2 syncode done"
