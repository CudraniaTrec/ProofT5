#!/usr/bin/env bash
# Start the OLMo-3-1125-32B matrix after the ModelScope snapshot is complete
# and a free H200 is available.  GPU 0 is currently free, so this can run in
# parallel with the Qwen3-30B-A3B matrix on GPU 6.
set -u
ROOT=/data2/x/hzc
REPO=$ROOT/prooft5
MODEL=$ROOT/hf_models/Olmo-3-1125-32B
while :; do
  n=$(find "$MODEL" -maxdepth 1 -type f -name '*.safetensors' | wc -l)
  incomplete=$(find "$MODEL" -maxdepth 2 -type f \( -name '*.aria2' -o -name '*.incomplete' \) | head -1)
  if [ "$n" -eq 14 ] && [ -z "$incomplete" ] && [ -s "$MODEL/config.json" ]; then break; fi
  echo "WAITING_OLMO shards=$n/14 incomplete=${incomplete:-none}"
  sleep 60
done
while :; do
  used=$(nvidia-smi --id=0 --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null | tr -d ' ' | head -1)
  if [ -n "$used" ] && [ "$used" -lt 2048 ]; then break; fi
  echo "WAITING_OLMO_GPU gpu=0 memory=${used:-unknown}MiB"
  sleep 60
done
exec "$REPO/scripts/ensure_large_decoder_matrix_20260901.sh" \
  "$MODEL" olmo3_1125_32b 0 olmo3-1125-32b prefix_completion
