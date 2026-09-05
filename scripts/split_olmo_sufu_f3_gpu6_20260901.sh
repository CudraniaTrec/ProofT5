#!/usr/bin/env bash
# Parallelize OLMo's expensive SuFu three-shot pass after its zero-shot pass.
set -u
ROOT=/data2/x/hzc
REPO=$ROOT/prooft5
ART=$REPO/artifacts/major_revision_decoder_only_multibenchmark_20260828
while [ ! -s "$ART/olmo3_1125_32b_sufu_zero_score.json" ]; do sleep 5; done
kill -TERM 3336684 3336698 2>/dev/null || true
sleep 5
for pid in $(pgrep -f 'run_decoder_only_sufu.py.*olmo3_1125_32b_sufu_f3_20260901' || true); do kill -TERM "$pid" 2>/dev/null || true; done
exec "$REPO/scripts/run_single_large_condition_20260901.sh" \
  "$ROOT/hf_models/Olmo-3-1125-32B" olmo3_1125_32b 6 olmo3-1125-32b prefix_completion sufu_f3
