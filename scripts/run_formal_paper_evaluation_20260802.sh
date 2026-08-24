#!/usr/bin/env bash
# Complete the audited SuFu training route, then evaluate every formal Java
# and SuFu checkpoint on the frozen paper tests and their overlap partitions.

set -euo pipefail

cd /data2/x/hzc/prooft5

PY=/data2/x/hzc/.uv-envs/prooft5-t5gemma-py313/bin/python
TRAIN_SESSION=sufu_formal10_20260802
SUFU_TASK=sufucoqview_complete281_from_sufu100_fullseq_20260801
SUFU_MODEL=sufucoqview_complete281_from_sufu100_fullseq_20260801_sufu_fullseq_b1_lr5em6_pass10_20260802_205911
JAVA_TASK=mbjpcoqview_complete706_from_java30_fullseq_20260801
JAVA_MODEL=mbjpcoqview_complete706_from_java30_fullseq_20260801_java_fullseq_b1_lr1em6_pass10_20260802_092743
FINAL_LABEL=d2formal10final
EPOCH_LABEL=d2formal10epochs
EPOCHS=epoch0,epoch1,epoch2,epoch3,epoch4,epoch5,epoch6,epoch7,epoch8,epoch9

while tmux has-session -t "$TRAIN_SESSION" 2>/dev/null; do
  sleep 30
done

grep -q 'complete: checkpoints are in' \
  tmp/sufu_coqview_train_formal10_20260802_driver.log || {
    printf '[%s] SuFu formal training did not complete normally\n' "$(date -Iseconds)"
    exit 1
  }

"$PY" scripts/audit_complete_coqview_bounds.py \
  "Utils/data/${SUFU_TASK}" \
  --json_out "tmp/${SUFU_TASK}_bounds_audit.json" >/dev/null
"$PY" scripts/audit_complete_coqview_bounds.py \
  "Utils/data/${JAVA_TASK}" \
  --json_out "tmp/${JAVA_TASK}_bounds_audit.json" >/dev/null
printf '[%s] Java and SuFu sequence-bound audits passed\n' "$(date -Iseconds)"

SUFU_METRICS="tmp/${SUFU_MODEL}_metrics.jsonl"
"$PY" scripts/audit_complete_coqview_training.py "$SUFU_METRICS" \
  --real_rows 281 --ranks 8 --passes 10 \
  --expected_active_targets_per_pass 33519 \
  --train_pickle "Utils/data/${SUFU_TASK}/train.pkl" \
  --runtime_dir "tmp/runtime_state/${SUFU_MODEL}" \
  > "tmp/${SUFU_MODEL}_audit.json"
printf '[%s] SuFu 10-pass training audit passed\n' "$(date -Iseconds)"

SUFU_OVERLAP_INDICES="$("$PY" scripts/compute_exact_train_test_overlap.py \
  --task_dir "Utils/data/${SUFU_TASK}" \
  --expected_train 281 --expected_test 58 --expected_overlap 29 \
  --format indices)"
JAVA_OVERLAP_INDICES="$("$PY" scripts/compute_exact_train_test_overlap.py \
  --task_dir "Utils/data/${JAVA_TASK}" \
  --expected_train 706 --expected_test 67 --expected_overlap 33 \
  --format indices)"
printf '[%s] exact complete-row overlaps verified: SuFu=29, Java=33\n' \
  "$(date -Iseconds)"

preflight_output_tags_absent() {
  local task="$1"
  local model="$2"
  local kinds="$3"
  local label="$4"
  local -a kind_array
  IFS=',' read -r -a kind_array <<< "$kinds"
  for kind in "${kind_array[@]}"; do
    local tag="papercheck_${model}_${kind}_b10_lp0p1_${label}"
    local output_dir="Utils/output/${task}_test_ans/${tag}"
    if [ -e "$output_dir" ]; then
      printf 'formal output target already exists: %s\n' "$output_dir" >&2
      return 1
    fi
    local artifact
    for artifact in \
      "tmp/${tag}_score_timeout1.json" \
      "tmp/${tag}_score_timeout10.json" \
      "tmp/${tag}_overlap_score_timeout10.json" \
      "tmp/${tag}_nonoverlap_score_timeout10.json"; do
      if [ -e "$artifact" ]; then
        printf 'formal score target already exists: %s\n' "$artifact" >&2
        return 1
      fi
    done
  done
}

preflight_output_tags_absent "$SUFU_TASK" "$SUFU_MODEL" final "$FINAL_LABEL"
preflight_output_tags_absent "$JAVA_TASK" "$JAVA_MODEL" final "$FINAL_LABEL"
preflight_output_tags_absent "$SUFU_TASK" "$SUFU_MODEL" "$EPOCHS" "$EPOCH_LABEL"
preflight_output_tags_absent "$JAVA_TASK" "$JAVA_MODEL" "$EPOCHS" "$EPOCH_LABEL"
printf '[%s] all 22 formal evaluation target tags are unused\n' "$(date -Iseconds)"

run_sweep() {
  local task="$1"
  local model="$2"
  local branch="$3"
  local kinds="$4"
  local label="$5"
  COQVIEW_SWEEP_KINDS="$kinds" \
  COQVIEW_SWEEP_LENGTH_PENALTIES=0.1 \
  COQVIEW_SWEEP_LABEL="$label" \
  COQVIEW_SCORE_TIMEOUTS=1,10 \
    bash scripts/sweep_complete_coqview_checkpoints.sh \
      "$task" "$model" "$branch"
}

require_pass1_at_least() {
  local score_json="$1"
  local threshold="$2"
  "$PY" - "$score_json" "$threshold" <<'PY'
import json
import sys

path, threshold = sys.argv[1], float(sys.argv[2])
result = json.load(open(path))
observed = float(result["pass1"])
print(f"health gate: {path}: pass1={observed:.6f}, required>={threshold:.6f}")
if observed < threshold:
    raise SystemExit(1)
PY
}

require_metric_at_most() {
  local score_json="$1"
  local metric="$2"
  local threshold="$3"
  "$PY" - "$score_json" "$metric" "$threshold" <<'PY'
import json
import sys

path, metric, threshold = sys.argv[1], sys.argv[2], float(sys.argv[3])
result = json.load(open(path))
observed = float(result[metric])
print(
    f"health gate: {path}: {metric}={observed:.6f}, "
    f"required<={threshold:.6f}"
)
if observed > threshold:
    raise SystemExit(1)
PY
}

score_subsets() {
  local branch="$1"
  local task="$2"
  local output_tag="$3"
  local overlap_indices="$4"
  local problem_count="$5"
  local full_score="tmp/${output_tag}_score_timeout10.json"
  local nonoverlap_indices
  local -a checkpoint_metadata
  mapfile -t checkpoint_metadata < <("$PY" - "$full_score" <<'PY'
import json
import sys

score = json.load(open(sys.argv[1]))
for key in (
    "model_output_task",
    "model_type",
    "train_time",
    "checkpoint_epoch",
    "model_checkpoint_path",
    "model_checkpoint_sha256",
):
    value = score.get(key, "")
    print("" if value is None else value)
PY
)
  local -a score_metadata_args=(
    --model_output_task "${checkpoint_metadata[0]}"
    --model_type "${checkpoint_metadata[1]}"
    --train_time "${checkpoint_metadata[2]}"
    --model_checkpoint_path "${checkpoint_metadata[4]}"
    --model_checkpoint_sha256 "${checkpoint_metadata[5]}"
  )
  if [ -n "${checkpoint_metadata[3]}" ]; then
    score_metadata_args+=(--checkpoint_epoch "${checkpoint_metadata[3]}")
  fi
  nonoverlap_indices="$("$PY" - "$overlap_indices" "$problem_count" <<'PY'
import sys

overlap = {int(value) for value in sys.argv[1].split(",") if value}
print(",".join(str(index) for index in range(int(sys.argv[2])) if index not in overlap))
PY
)"
  if [ "$branch" = sufu ]; then
    "$PY" score_sufu_no_write.py --task "$task" --split test \
      --output_tag "$output_tag" --pass_at_k 10 --workers 32 --timeout 10 \
      "${score_metadata_args[@]}" \
      --indices "$overlap_indices" \
      --json_out "tmp/${output_tag}_overlap_score_timeout10.json"
    "$PY" score_sufu_no_write.py --task "$task" --split test \
      --output_tag "$output_tag" --pass_at_k 10 --workers 32 --timeout 10 \
      "${score_metadata_args[@]}" \
      --indices "$nonoverlap_indices" \
      --json_out "tmp/${output_tag}_nonoverlap_score_timeout10.json"
  else
    "$PY" score_java_no_write.py --task "$task" --split test \
      --output_tag "$output_tag" --pass_at_k 10 --workers 64 --timeout 10 \
      "${score_metadata_args[@]}" \
      --indices "$overlap_indices" \
      --json_out "tmp/${output_tag}_overlap_score_timeout10.json"
    "$PY" score_java_no_write.py --task "$task" --split test \
      --output_tag "$output_tag" --pass_at_k 10 --workers 64 --timeout 10 \
      "${score_metadata_args[@]}" \
      --indices "$nonoverlap_indices" \
      --json_out "tmp/${output_tag}_nonoverlap_score_timeout10.json"
  fi
}

# Test the newly trained branch first.  The frozen SuFu test has 29/58 exact
# train overlaps, so a final model that learned the requested data should be
# near one half at rank one before any paper-clean subset analysis.
run_sweep "$SUFU_TASK" "$SUFU_MODEL" sufu final "$FINAL_LABEL"
SUFU_FINAL_TAG="papercheck_${SUFU_MODEL}_final_b10_lp0p1_${FINAL_LABEL}"
require_pass1_at_least "tmp/${SUFU_FINAL_TAG}_score_timeout10.json" 0.45
score_subsets sufu "$SUFU_TASK" "$SUFU_FINAL_TAG" \
  "$SUFU_OVERLAP_INDICES" \
  58
require_pass1_at_least \
  "tmp/${SUFU_FINAL_TAG}_overlap_score_timeout10.json" 0.90
require_metric_at_most \
  "tmp/${SUFU_FINAL_TAG}_score_timeout10.json" compile_error_rate 0

# Java already passed a beam-1 overlap-memory diagnostic (32/33), but its
# formal beam-10 output must independently clear the same broad health gate.
run_sweep "$JAVA_TASK" "$JAVA_MODEL" java final "$FINAL_LABEL"
JAVA_FINAL_TAG="papercheck_${JAVA_MODEL}_final_b10_lp0p1_${FINAL_LABEL}"
require_pass1_at_least "tmp/${JAVA_FINAL_TAG}_score_timeout10.json" 0.45
score_subsets java "$JAVA_TASK" "$JAVA_FINAL_TAG" \
  "$JAVA_OVERLAP_INDICES" \
  67
require_pass1_at_least \
  "tmp/${JAVA_FINAL_TAG}_overlap_score_timeout10.json" 0.90

# Only after both final checkpoints pass the training-memory sanity gate do we
# spend compute on the per-pass trajectory needed for checkpoint selection.
run_sweep "$SUFU_TASK" "$SUFU_MODEL" sufu "$EPOCHS" "$EPOCH_LABEL"
run_sweep "$JAVA_TASK" "$JAVA_MODEL" java "$EPOCHS" "$EPOCH_LABEL"

IFS=',' read -r -a EPOCH_ARRAY <<< "$EPOCHS"
for kind in "${EPOCH_ARRAY[@]}"; do
  SUFU_EPOCH_TAG="papercheck_${SUFU_MODEL}_${kind}_b10_lp0p1_${EPOCH_LABEL}"
  score_subsets sufu "$SUFU_TASK" "$SUFU_EPOCH_TAG" \
    "$SUFU_OVERLAP_INDICES" \
    58
  JAVA_EPOCH_TAG="papercheck_${JAVA_MODEL}_${kind}_b10_lp0p1_${EPOCH_LABEL}"
  score_subsets java "$JAVA_TASK" "$JAVA_EPOCH_TAG" \
    "$JAVA_OVERLAP_INDICES" \
    67
done

"$PY" scripts/summarize_formal_paper_checkpoints.py --branch sufu \
  --full_glob "tmp/papercheck_${SUFU_MODEL}_final_b10_lp0p1_${FINAL_LABEL}_score_timeout10.json" \
  --full_glob "tmp/papercheck_${SUFU_MODEL}_epoch*_b10_lp0p1_${EPOCH_LABEL}_score_timeout10.json" \
  --nonoverlap_glob "tmp/papercheck_${SUFU_MODEL}_final_b10_lp0p1_${FINAL_LABEL}_nonoverlap_score_timeout10.json" \
  --nonoverlap_glob "tmp/papercheck_${SUFU_MODEL}_epoch*_b10_lp0p1_${EPOCH_LABEL}_nonoverlap_score_timeout10.json" \
  --json_out "tmp/${SUFU_MODEL}_formal_paper_comparison.json" \
  --markdown_out "tmp/${SUFU_MODEL}_formal_paper_comparison.md"

"$PY" scripts/summarize_formal_paper_checkpoints.py --branch java \
  --full_glob "tmp/papercheck_${JAVA_MODEL}_final_b10_lp0p1_${FINAL_LABEL}_score_timeout10.json" \
  --full_glob "tmp/papercheck_${JAVA_MODEL}_epoch*_b10_lp0p1_${EPOCH_LABEL}_score_timeout10.json" \
  --nonoverlap_glob "tmp/papercheck_${JAVA_MODEL}_final_b10_lp0p1_${FINAL_LABEL}_nonoverlap_score_timeout10.json" \
  --nonoverlap_glob "tmp/papercheck_${JAVA_MODEL}_epoch*_b10_lp0p1_${EPOCH_LABEL}_nonoverlap_score_timeout10.json" \
  --json_out "tmp/${JAVA_MODEL}_formal_paper_comparison.json" \
  --markdown_out "tmp/${JAVA_MODEL}_formal_paper_comparison.md"

printf '[%s] all formal final and checkpoint evaluations completed\n' \
  "$(date -Iseconds)"
