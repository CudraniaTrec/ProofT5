#!/bin/bash
# Sequential 220M timing runs: base -> grammar -> type -> dynamic, one GPU.
cd /data2/x/hzc/prooft5
PY=/data2/x/hzc/.uv-envs/prooft5-py313/bin/python
for cfg in base grammar type dynamic; do
  echo "=== $cfg start $(date +%H:%M:%S) ==="
  CUDA_VISIBLE_DEVICES=0 PROOFT5_COLLECT_DECODE_STATS=1 \
    PROOFT5_SUFU_STATS_OUT=tmp/rq2_runtime_220m/rq2_runtime_220m_${cfg}.jsonl \
    $PY run.py --task rq2sufu220m_${cfg} --eval --no_swanlab --disable_tqdm \
    --model_output_task sufucoqview > tmp/rq2_runtime_220m/${cfg}.out 2>&1
  echo "=== $cfg exit=$? $(date +%H:%M:%S) ==="
done
echo "ALL DONE $(date +%H:%M:%S)"
