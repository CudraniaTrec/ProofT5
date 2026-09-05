#!/usr/bin/env bash
# Once the sequential Qwen3-32B driver finishes SuFu zero-shot, move its
# remaining F3 condition to a free H200 so it can finish independently.
set -u
ROOT=/data2/x/hzc
REPO=$ROOT/prooft5
ART=$REPO/artifacts/major_revision_decoder_only_multibenchmark_20260828
while [ ! -s "$ART/qwen3_32b_sufu_zero_score.json" ]; do sleep 5; done
# Stop only the old sequential driver and its just-finished child.  The score
# file is already durable, so no generated candidate is discarded.
kill -TERM 3095069 3202120 2>/dev/null || true
sleep 5
for pid in $(pgrep -f 'run_decoder_only_sufu.py.*qwen3_32b_sufu_f3_20260901' || true); do kill -TERM "$pid" 2>/dev/null || true; done
exec "$REPO/scripts/run_single_large_condition_20260901.sh" \
  "$ROOT/hf_models/Qwen3-32B" qwen3_32b 1 qwen3-32b full_source_plain sufu_f3
