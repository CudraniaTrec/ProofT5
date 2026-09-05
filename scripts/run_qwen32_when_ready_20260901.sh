#!/usr/bin/env bash
# Launch Qwen3-32B as soon as its independent download is complete.  The
# main candidate orchestrator may later encounter the same complete row and
# safely resume it without changing any generated candidate.
set -u
ROOT=/data2/x/hzc
REPO=$ROOT/prooft5
MODEL=$ROOT/hf_models/Qwen3-32B
while :; do
  n=$(find "$MODEL" -maxdepth 1 -type f -name '*.safetensors' | wc -l)
  incomplete=$(find "$MODEL" -maxdepth 2 -type f \( -name '*.aria2' -o -name '*.incomplete' \) | head -1)
  if [ "$n" -eq 17 ] && [ -z "$incomplete" ] && [ -s "$MODEL/config.json" ]; then break; fi
  echo "WAITING_QWEN32 shards=$n/17 incomplete=${incomplete:-none}"
  sleep 60
done
while :; do
  used=$(nvidia-smi --id=3 --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null | tr -d ' ' | head -1)
  if [ -n "$used" ] && [ "$used" -lt 2048 ]; then break; fi
  echo "WAITING_QWEN32_GPU memory=${used:-unknown}MiB"
  sleep 60
done
exec "$REPO/scripts/ensure_large_decoder_matrix_20260901.sh" \
  "$MODEL" qwen3_32b 3 qwen3-32b full_source_plain
