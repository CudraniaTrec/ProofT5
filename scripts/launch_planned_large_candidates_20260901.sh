#!/usr/bin/env bash
# Start the remaining planned large-model matrices as soon as their
# ModelScope downloads are complete.  This is intentionally additive and
# never removes or overwrites existing outputs; every matrix uses --resume.
set -u

ROOT=/data2/x/hzc
REPO=/data2/x/hzc/prooft5
ART=$REPO/artifacts/major_revision_decoder_only_multibenchmark_20260828

wait_complete() {
  local path=$1 expected=$2 label=$3
  while :; do
    local n incomplete
    n=$(find "$path" -maxdepth 1 -type f -name '*.safetensors' | wc -l)
    incomplete=$(find "$path" -maxdepth 2 -type f \( -name '*.aria2' -o -name '*.incomplete' \) | head -1)
    if [ "$n" -eq "$expected" ] && [ -z "$incomplete" ] && [ -s "$path/config.json" ]; then
      echo "CANDIDATE_READY $label shards=$n"
      return 0
    fi
    echo "WAITING $label shards=$n/$expected incomplete=${incomplete:-none}"
    sleep 60
  done
}

wait_gpu_free() {
  local gpu=$1 label=$2
  while :; do
    local used
    used=$(nvidia-smi --id="$gpu" --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null | tr -d ' ' | head -1)
    if [ -n "$used" ] && [ "$used" -lt 2048 ]; then
      echo "GPU_READY $label gpu=$gpu memory=${used}MiB"
      return 0
    fi
    echo "WAITING_GPU $label gpu=$gpu memory=${used:-unknown}MiB"
    sleep 60
  done
}

run_one() {
  local model=$1 slug=$2 gpu=$3 model_type=$4 mode=$5
  echo "START_MATRIX $slug gpu=$gpu mode=$mode"
  "$REPO/scripts/ensure_large_decoder_matrix_20260901.sh" \
    "$model" "$slug" "$gpu" "$model_type" "$mode"
  echo "END_MATRIX $slug rc=$?"
}

# GPU 6 is reserved for the first 30B-class candidate.  GPU 3 is used for
# Qwen3-32B after its download so it does not wait for the supplemental
# Qwen3.6/Qwen3.8 GFG jobs currently sharing GPU 0; OLMo then reuses GPU 6
# after Qwen3-30B.
wait_complete "$ROOT/hf_models/Qwen3-30B-A3B-Base" 16 qwen3-30b-a3b-base
wait_gpu_free 6 qwen3-30b-a3b-base
run_one "$ROOT/hf_models/Qwen3-30B-A3B-Base" qwen3_30b_a3b_base 6 qwen3-30b-a3b-base prefix_completion

wait_complete "$ROOT/hf_models/Qwen3-32B" 17 qwen3-32b
wait_gpu_free 0 qwen3-32b
run_one "$ROOT/hf_models/Qwen3-32B" qwen3_32b 3 qwen3-32b full_source_plain

wait_complete "$ROOT/hf_models/Olmo-3-1125-32B" 14 olmo-3-1125-32b
wait_gpu_free 6 olmo-3-1125-32b
run_one "$ROOT/hf_models/Olmo-3-1125-32B" olmo3_1125_32b 6 olmo-3-1125-32b prefix_completion

echo 'PLANNED_LARGE_CANDIDATES_COMPLETE'
