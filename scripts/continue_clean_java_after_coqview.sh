#!/usr/bin/env bash
# Continue the clean Java reproduction after the active CoqView run completes.

set -euo pipefail

if [ "$#" -ne 1 ] || ! [[ "$1" =~ ^[1-9][0-9]*$ ]]; then
  printf 'usage: %s ACTIVE_COQVIEW_LAUNCHER_PID\n' "$0" >&2
  exit 64
fi

cd /data2/x/hzc/prooft5

WATCH_PID="$1"
PY=/data2/x/hzc/.uv-envs/prooft5-t5gemma-py313/bin/python
CV_TASK=mbjpcoqview_clean673_from_java_clean30_fullseq_20260810
CV_MODEL=mbjpcoqview_clean673_from_java_clean30_fullseq_20260810_java_fullseq_b1_lr1em6_pass10_20260810_160322
CV_LOG="tmp/${CV_MODEL}.log"
CV_METRICS="tmp/${CV_MODEL}_metrics.jsonl"
CV_RUNTIME="tmp/runtime_state/${CV_MODEL}"
CV_CHECKPOINT="Utils/models/Model${CV_MODEL}/last_model.ckpt"
CV_FINAL_AUDIT="tmp/${CV_MODEL}_audit_final10.json"
COQ_MODEL=mbjp_humaneval_half_train_t5gemma2_20260731_clean673_noleak_formal30_8gpu_b5_lr1em5_20260810
PLAIN_STAMP=20260811_after_clean_coqview
PLAIN_MODEL=t5gemma2-2b_java_clean673_noleak_b5_lr5em5_pass30_${PLAIN_STAMP}
PLAIN_CHECKPOINT="t5_llm/models/${PLAIN_MODEL}"
FINAL_JSON=tmp/clean_java_reproduction_final_20260811.json
FINAL_MARKDOWN=docs/experiments/CLEAN_JAVA_REPRODUCTION_RESULTS_20260811.md
PLAIN_MBJP_TAG=cleanrepro_plain_mbjp_final_b10_20260811
PLAIN_HE_TAG=cleanrepro_plain_humaneval_final_b10_20260811
COQ_MBJP_TAG=cleanrepro_coq_mbjp_final_b10_lp0p1_20260811
COQ_HE_TAG=cleanrepro_coq_humaneval_final_b10_lp0p1_20260811
CV_MBJP_TAG=cleanrepro_coqview_mbjp_final_b10_lp0p1_20260811
CV_HE_TAG=cleanrepro_coqview_humaneval_final_b10_lp0p1_20260811

if [ ! -r "/proc/${WATCH_PID}/cmdline" ]; then
  printf 'watched CoqView launcher pid is not active: %s\n' "$WATCH_PID" >&2
  exit 66
fi
if ! tr '\0' ' ' < "/proc/${WATCH_PID}/cmdline" | grep -Fq "$CV_TASK"; then
  printf 'pid %s is not the expected CoqView launcher\n' "$WATCH_PID" >&2
  exit 65
fi
for path in "$FINAL_JSON" "$FINAL_MARKDOWN" "$PLAIN_CHECKPOINT" "$CV_FINAL_AUDIT"; do
  if [ -e "$path" ]; then
    printf 'refusing to overwrite post-training artifact: %s\n' "$path" >&2
    exit 73
  fi
done
for tag in \
  "$PLAIN_MBJP_TAG" "$PLAIN_HE_TAG" "$COQ_MBJP_TAG" "$COQ_HE_TAG" \
  "$CV_MBJP_TAG" "$CV_HE_TAG"; do
  if [ -e "tmp/${tag}_score_timeout10.json" ]; then
    printf 'refusing to overwrite score artifact: %s\n' \
      "tmp/${tag}_score_timeout10.json" >&2
    exit 73
  fi
done

printf '[%s] waiting for pid=%s model=%s\n' \
  "$(date -Iseconds)" "$WATCH_PID" "$CV_MODEL"
while kill -0 "$WATCH_PID" 2>/dev/null; do
  sleep 30
done
sleep 5

if ! grep -Fq "complete: checkpoints are in Utils/models/Model${CV_MODEL}" "$CV_LOG"; then
  printf 'CoqView launcher ended without its normal completion marker\n' >&2
  exit 1
fi
if [ ! -f "$CV_CHECKPOINT" ]; then
  printf 'final CoqView checkpoint is absent: %s\n' "$CV_CHECKPOINT" >&2
  exit 66
fi

"$PY" scripts/audit_complete_coqview_training.py "$CV_METRICS" \
  --real_rows 673 --ranks 8 --passes 10 \
  --expected_active_targets_per_pass 71234 \
  --train_pickle "Utils/data/${CV_TASK}/train.pkl" \
  --runtime_dir "$CV_RUNTIME" \
  > "$CV_FINAL_AUDIT"
jq -e '.status == "ok" and .loss_records == 850 and .passes == 10' \
  "$CV_FINAL_AUDIT" >/dev/null
CV_SHA="$(sha256sum "$CV_CHECKPOINT" | awk '{print $1}')"
printf '[%s] CoqView final audit passed, sha256=%s\n' \
  "$(date -Iseconds)" "$CV_SHA"

while :; do
  occupied=0
  for gpu in 0 1 2 3 4 5 6 7; do
    used="$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i "$gpu" | tr -d ' ')"
    if [ "$used" -ge 1024 ]; then
      occupied=1
    fi
  done
  if [ "$occupied" -eq 0 ]; then
    break
  fi
  sleep 30
done

printf '[%s] starting ordinary T5Gemma2 training\n' "$(date -Iseconds)"
CLEAN_JAVA_PLAIN_STAMP="$PLAIN_STAMP" \
  scripts/run_clean_java_plain_t5gemma2.sh

scripts/evaluate_clean_java_plain_checkpoint.sh \
  "$PLAIN_CHECKPOINT" java_mbjp_test "$PLAIN_MBJP_TAG"
scripts/evaluate_clean_java_plain_checkpoint.sh \
  "$PLAIN_CHECKPOINT" java_humaneval_test "$PLAIN_HE_TAG"

scripts/evaluate_clean_java_proof_checkpoint.sh \
  mbjp_original_test_t5gemma2_20260731 "$COQ_MODEL" coq "$COQ_MBJP_TAG"
scripts/evaluate_clean_java_proof_checkpoint.sh \
  humaneval_half_test_t5gemma2_20260731 "$COQ_MODEL" coq "$COQ_HE_TAG"
scripts/evaluate_clean_java_proof_checkpoint.sh \
  mbjp_original_test_coqview_cleanjava_20260810 "$CV_MODEL" coqview "$CV_MBJP_TAG"
scripts/evaluate_clean_java_proof_checkpoint.sh \
  humaneval_half_test_coqview_cleanjava_20260810 "$CV_MODEL" coqview "$CV_HE_TAG"

"$PY" scripts/summarize_clean_java_reproduction.py \
  --mbjp_plain "tmp/${PLAIN_MBJP_TAG}_score_timeout10.json" \
  --mbjp_coq "tmp/${COQ_MBJP_TAG}_score_timeout10.json" \
  --mbjp_coqview "tmp/${CV_MBJP_TAG}_score_timeout10.json" \
  --humaneval_plain "tmp/${PLAIN_HE_TAG}_score_timeout10.json" \
  --humaneval_coq "tmp/${COQ_HE_TAG}_score_timeout10.json" \
  --humaneval_coqview "tmp/${CV_HE_TAG}_score_timeout10.json" \
  --json_out "$FINAL_JSON" --markdown_out "$FINAL_MARKDOWN"

printf '[%s] clean Java reproduction complete: %s\n' \
  "$(date -Iseconds)" "$FINAL_MARKDOWN"
