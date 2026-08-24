#!/usr/bin/env bash
# Screen all ten saved SuFu checkpoints on the six final-checkpoint rank failures.

set -euo pipefail

cd /data2/x/hzc/prooft5
TASK=sufucoqview_complete281_from_sufu100_fullseq_20260801
MODEL=sufucoqview_complete281_from_sufu100_fullseq_20260801_sufu_fullseq_b1_lr5em6_pass10_20260802_205911
INDICES=10,19,26,32,48,52
LABEL=d5failure6
PY=/data2/x/hzc/.uv-envs/prooft5-t5gemma-py313/bin/python
ACC=/data2/x/hzc/.uv-envs/prooft5-t5gemma-py313/bin/accelerate
GPUS="${COQVIEW_SWEEP_GPUS:-0,1,2,3}"
NUM_PROCESSES="${COQVIEW_SWEEP_NUM_PROCESSES:-4}"
PORT="${COQVIEW_SWEEP_PORT:-29731}"
MODEL_ROOT="Utils/models/Model${MODEL}"

mapfile -t RUN_DIRS < <(find "$MODEL_ROOT" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort)
if [ "${#RUN_DIRS[@]}" -ne 1 ]; then
  printf 'expected one timestamped run under %s, got %s\n' "$MODEL_ROOT" "${#RUN_DIRS[@]}" >&2
  exit 65
fi
RUN_DIR="${RUN_DIRS[0]}"

for epoch in {0..9}; do
  TAG="papercheck_${MODEL}_epoch${epoch}_b10_lp0p1_${LABEL}"
  for path in \
    "Utils/output/${TASK}_test_ans/${TAG}" \
    "tmp/${TAG}_surface_audit.json" \
    "tmp/${TAG}_score_timeout10.json"; do
    if [ -e "$path" ]; then
      printf 'refusing to overwrite %s\n' "$path" >&2
      exit 73
    fi
  done
  if [ ! -f "$MODEL_ROOT/$RUN_DIR/epoch${epoch}_model.ckpt" ]; then
    printf 'checkpoint absent: epoch%s\n' "$epoch" >&2
    exit 66
  fi
done

for epoch in {0..9}; do
  TAG="papercheck_${MODEL}_epoch${epoch}_b10_lp0p1_${LABEL}"
  CHECKPOINT="$MODEL_ROOT/$RUN_DIR/epoch${epoch}_model.ckpt"
  CHECKPOINT_SHA="$(sha256sum "$CHECKPOINT" | awk '{print $1}')"
  printf '[%s] screening epoch%s (%s)\n' "$(date -Iseconds)" "$epoch" "$CHECKPOINT_SHA"

  CUDA_VISIBLE_DEVICES="$GPUS" \
  OMP_NUM_THREADS=8 MKL_NUM_THREADS=8 OPENBLAS_NUM_THREADS=8 NUMEXPR_NUM_THREADS=8 \
  TOKENIZERS_PARALLELISM=false PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
  PROOFT5_DISTRIBUTED_TIMEOUT_MINUTES=720 \
  "$ACC" launch --config_file tmp/acc_config_ddp_bf16.yaml \
    --num_processes "$NUM_PROCESSES" --main_process_port "$PORT" run.py \
    --eval --task "$TASK" --model_output_task "$MODEL" \
    --train_time "$RUN_DIR" --checkpoint_epoch "$epoch" \
    --eval_split test --eval_indices "$INDICES" --output_tag "$TAG" \
    --beam_size 10 --length_penalty 0.1 --coq_candidate_multiplier 20 \
    --force_sufu_type_check --batch_size_eval 1 --eval_num_workers 0 \
    --runtime_dir "tmp/runtime_state/${TAG}" --disable_tqdm --no_swanlab

  "$PY" scripts/audit_sufu_generated_candidates.py \
    --task "$TASK" --split test --output_tag "$TAG" --beam_size 10 \
    --indices "$INDICES" --require_beam_metadata \
    --json_out "tmp/${TAG}_surface_audit.json"

  "$PY" score_sufu_no_write.py --task "$TASK" --split test \
    --output_tag "$TAG" --pass_at_k 10 --workers 12 --timeout 10 \
    --indices "$INDICES" --model_output_task "$MODEL" \
    --model_type "epoch${epoch}" --train_time "$RUN_DIR" \
    --checkpoint_epoch "$epoch" --model_checkpoint_path "$CHECKPOINT" \
    --model_checkpoint_sha256 "$CHECKPOINT_SHA" \
    --json_out "tmp/${TAG}_score_timeout10.json"
done

"$PY" - "$MODEL" "$LABEL" <<'PY'
import glob
import json
import sys
from pathlib import Path

model, label = sys.argv[1:]
rows = []
for path_text in glob.glob(
    f"tmp/papercheck_{model}_epoch*_b10_lp0p1_{label}_score_timeout10.json"
):
    path = Path(path_text)
    score = json.loads(path.read_text())
    rows.append(
        {
            "checkpoint": score["model_type"],
            "pass1": score["pass1"],
            "pass10": score["pass10"],
            "top1_solved": score["top1_solved"],
            "solved": score["solved"],
            "compile_error_rate": score["compile_error_rate"],
            "artifact": str(path),
        }
    )
rows.sort(key=lambda row: int(row["checkpoint"].removeprefix("epoch")))
summary = {
    "scope": "six final-checkpoint overlap rank failures",
    "problem_ids": [10, 19, 26, 32, 48, 52],
    "rows": rows,
    "best_pass1": max((row["pass1"] for row in rows), default=0.0),
}
out = Path(f"tmp/{model}_{label}_summary.json")
out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
print(json.dumps(summary, indent=2, sort_keys=True))
PY
