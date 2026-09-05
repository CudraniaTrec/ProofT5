#!/usr/bin/env bash
# Keep a large-model matrix alive across an external session timeout or a
# single-condition failure.  Completed conditions are skipped by --resume.
set -u

if [ "$#" -lt 4 ]; then
  echo "usage: $0 MODEL_PATH MODEL_SLUG GPU MODEL_TYPE [COMPLETION_MODE]" >&2
  exit 2
fi

MODEL=$1
SLUG=$2
GPU=$3
MODEL_TYPE=$4
MODE=${5:-full_source}
ART=/data2/x/hzc/prooft5/artifacts/major_revision_decoder_only_multibenchmark_20260828
PY=/data2/x/hzc/.uv-envs/prooft5-t5gemma-py313/bin/python

expected=(
  "${SLUG}_mbjp_zero_score.json"
  "${SLUG}_mbjp_f3_score.json"
  "${SLUG}_he_zero_score.json"
  "${SLUG}_he_f3_score.json"
  "${SLUG}_gfg_zero_score.json"
  "${SLUG}_gfg_f3_score.json"
  "${SLUG}_sufu_zero_score.json"
  "${SLUG}_sufu_f3_score.json"
)

while :; do
  missing=0
  for name in "${expected[@]}"; do
    if [ ! -s "$ART/$name" ]; then missing=$((missing + 1)); fi
  done
  valid=0
  if [ "$missing" -eq 0 ] && "$PY" /data2/x/hzc/prooft5/scripts/validate_large_decoder_matrix_20260901.py --slug "$SLUG" >/tmp/validate_${SLUG}_20260901.txt 2>&1; then
    valid=1
  fi
  if [ "$missing" -eq 0 ] && [ "$valid" -eq 1 ]; then
    echo "MATRIX_COMPLETE $SLUG"
    exit 0
  fi
  echo "MATRIX_RETRY $SLUG missing=$missing valid=$valid"
  /data2/x/hzc/prooft5/scripts/run_large_decoder_matrix_20260901.sh \
    "$MODEL" "$SLUG" "$GPU" "$MODEL_TYPE" "$MODE"
  rc=$?
  echo "MATRIX_ATTEMPT_EXIT $SLUG rc=$rc"
  sleep 5
done
