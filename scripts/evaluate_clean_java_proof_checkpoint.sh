#!/usr/bin/env bash
# Evaluate one frozen Java ProofT5/T5Gemma2 checkpoint with a beam of ten.
#
# Usage:
#   scripts/evaluate_clean_java_proof_checkpoint.sh \
#     TEST_TASK MODEL_OUTPUT_TASK coq|coqview OUTPUT_TAG

set -euo pipefail

if [ "$#" -ne 4 ]; then
  printf 'usage: %s TEST_TASK MODEL_OUTPUT_TASK coq|coqview OUTPUT_TAG\n' "$0" >&2
  exit 64
fi

EVAL_TASK="$1"
EVAL_MODEL="$2"
EVAL_MODE="$3"
EVAL_TAG="$4"
case "$EVAL_MODE" in
  coq|coqview) ;;
  *) printf 'mode must be coq or coqview\n' >&2; exit 64 ;;
esac
if ! [[ "$EVAL_TAG" =~ ^[A-Za-z0-9._-]+$ ]]; then
  printf 'output tag must be filename-safe\n' >&2
  exit 64
fi

cd /data2/x/hzc/prooft5

EVAL_PY=/data2/x/hzc/.uv-envs/prooft5-t5gemma-py313/bin/python
EVAL_ACC=/data2/x/hzc/.uv-envs/prooft5-t5gemma-py313/bin/accelerate
EVAL_GPUS="${CLEAN_JAVA_EVAL_GPUS:-0,1,2,3,4,5,6,7}"
EVAL_PORT="${CLEAN_JAVA_EVAL_PORT:-29683}"
EVAL_TIMEOUT="${CLEAN_JAVA_SCORE_TIMEOUT:-10}"
EVAL_CANDIDATE_MULTIPLIER="${CLEAN_JAVA_CANDIDATE_MULTIPLIER:-20}"
EVAL_BEAM_SIZE="${CLEAN_JAVA_BEAM_SIZE:-10}"
EVAL_LENGTH_PENALTY="${CLEAN_JAVA_LENGTH_PENALTY:-0.1}"
EVAL_COQ_WORKERS="${CLEAN_JAVA_COQ_WORKERS:-8}"
EVAL_RESUME_OUTPUT="${CLEAN_JAVA_RESUME_OUTPUT:-0}"
EVAL_INDICES="${CLEAN_JAVA_EVAL_INDICES:-}"
EVAL_MAX_LEN="${CLEAN_JAVA_EVAL_MAX_LEN:-0}"
EVAL_FINAL_ONLY_COQ_CHECK="${CLEAN_JAVA_FINAL_ONLY_COQ_CHECK:-0}"
EVAL_CHECKPOINT="Utils/models/Model${EVAL_MODEL}/last_model.ckpt"
EVAL_OUTPUT="Utils/output/${EVAL_TASK}_test_ans/${EVAL_TAG}"
EVAL_SCORE="tmp/${EVAL_TAG}_score_timeout${EVAL_TIMEOUT}.json"
EVAL_RUNTIME="${CLEAN_JAVA_EVAL_RUNTIME:-tmp/runtime_state/${EVAL_TAG}}"

case "$EVAL_RESUME_OUTPUT" in
  0|1) ;;
  *) printf 'CLEAN_JAVA_RESUME_OUTPUT must be 0 or 1\n' >&2; exit 64 ;;
esac
case "$EVAL_FINAL_ONLY_COQ_CHECK" in
  0|1) ;;
  *) printf 'CLEAN_JAVA_FINAL_ONLY_COQ_CHECK must be 0 or 1\n' >&2; exit 64 ;;
esac
if [ "$EVAL_FINAL_ONLY_COQ_CHECK" -eq 1 ] && [ "$EVAL_MODE" != coq ]; then
  printf 'final-only Coq checking is available only in coq mode\n' >&2
  exit 64
fi

IFS=',' read -r -a EVAL_GPU_ARRAY <<< "$EVAL_GPUS"
EVAL_PROCESSES="${#EVAL_GPU_ARRAY[@]}"
if [ "$EVAL_PROCESSES" -lt 1 ]; then
  printf 'at least one GPU is required\n' >&2
  exit 64
fi
if [ "$EVAL_BEAM_SIZE" -lt 1 ]; then
  printf 'CLEAN_JAVA_BEAM_SIZE must be positive\n' >&2
  exit 64
fi
if [ "$EVAL_COQ_WORKERS" -lt 1 ]; then
  printf 'CLEAN_JAVA_COQ_WORKERS must be positive\n' >&2
  exit 64
fi
for path in "$EVAL_SCORE" "$EVAL_RUNTIME"; do
  if [ -e "$path" ]; then
    printf 'refusing to overwrite evaluation artifact: %s\n' "$path" >&2
    exit 73
  fi
done
if [ -e "$EVAL_OUTPUT" ] && [ "$EVAL_RESUME_OUTPUT" -ne 1 ]; then
  printf 'refusing to overwrite evaluation artifact: %s\n' "$EVAL_OUTPUT" >&2
  exit 73
fi
for path in \
  "Utils/data/${EVAL_TASK}/config.json" \
  "Utils/data/${EVAL_TASK}/test.pkl" \
  "$EVAL_CHECKPOINT"; do
  if [ ! -f "$path" ]; then
    printf 'required input is absent: %s\n' "$path" >&2
    exit 66
  fi
done

"$EVAL_PY" - "$EVAL_TASK" "$EVAL_MODE" <<'PY'
import json
import pickle
import sys
from pathlib import Path

task, mode = sys.argv[1:]
root = Path("Utils/data") / task
config = json.loads((root / "config.json").read_text())
with (root / "test.pkl").open("rb") as handle:
    rows = pickle.load(handle)
if not rows:
    raise SystemExit("test split is empty")
enabled = bool(config.get("enable_coqview", False))
if mode == "coqview" and not enabled:
    raise SystemExit("CoqView mode requires enable_coqview=true in the test task")
if mode == "coq" and enabled:
    raise SystemExit("Coq-only mode requires a test task without CoqView")
print({"task": task, "mode": mode, "test_rows": len(rows)})
PY

EVAL_EFFECTIVE_MAX_LEN="$($EVAL_PY - "$EVAL_TASK" "$EVAL_MAX_LEN" <<'PY'
import json
import sys
from pathlib import Path

task, override_text = sys.argv[1:]
override = int(override_text)
config = json.loads((Path("Utils/data") / task / "config.json").read_text())
effective = override or int(config.get("max_code_len", 0) or config["CodeLen"])
if effective <= 0:
    raise SystemExit("effective generation maximum must be positive")
print(effective)
PY
)"

EVAL_SHA="$(sha256sum "$EVAL_CHECKPOINT" | awk '{print $1}')"
printf '[%s] task=%s model=%s mode=%s checkpoint_sha256=%s\n' \
  "$(date -Iseconds)" "$EVAL_TASK" "$EVAL_MODEL" "$EVAL_MODE" "$EVAL_SHA"

EVAL_MODE_ARGS=()
if [ "$EVAL_MODE" = coq ]; then
  # Independent evaluation tasks intentionally have benchmark-oriented names.
  # Force the constrained decoder instead of relying on a "coq" name substring.
  EVAL_MODE_ARGS+=(--force_coq_decoder)
fi
if [ "$EVAL_FINAL_ONLY_COQ_CHECK" -eq 1 ]; then
  EVAL_MODE_ARGS+=(--coq_final_only_check)
fi
if [ "$EVAL_RESUME_OUTPUT" -eq 1 ]; then
  EVAL_MODE_ARGS+=(--resume_output)
fi
if [ -n "$EVAL_INDICES" ]; then
  EVAL_MODE_ARGS+=(--eval_indices "$EVAL_INDICES")
fi
if [ "$EVAL_MAX_LEN" -gt 0 ]; then
  EVAL_MODE_ARGS+=(--eval_max_len "$EVAL_MAX_LEN")
fi

CUDA_VISIBLE_DEVICES="$EVAL_GPUS" \
OMP_NUM_THREADS=8 MKL_NUM_THREADS=8 OPENBLAS_NUM_THREADS=8 NUMEXPR_NUM_THREADS=8 \
TOKENIZERS_PARALLELISM=false \
PROOFT5_DISTRIBUTED_TIMEOUT_MINUTES=720 \
TORCH_NCCL_HEARTBEAT_TIMEOUT_SEC=7200 \
TORCH_NCCL_ASYNC_ERROR_HANDLING=1 \
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
"$EVAL_ACC" launch --config_file tmp/acc_config_ddp_bf16.yaml \
  --num_processes "$EVAL_PROCESSES" --main_process_port "$EVAL_PORT" run.py \
  --eval --task "$EVAL_TASK" --model_output_task "$EVAL_MODEL" \
  --model_type last --eval_split test --output_tag "$EVAL_TAG" \
  --beam_size "$EVAL_BEAM_SIZE" --length_penalty "$EVAL_LENGTH_PENALTY" \
  --coq_candidate_multiplier "$EVAL_CANDIDATE_MULTIPLIER" \
  --coq_workers "$EVAL_COQ_WORKERS" --coq_timeout 20 \
  --runtime_dir "$EVAL_RUNTIME" --batch_size_eval 1 --eval_num_workers 0 \
  --disable_tqdm --no_swanlab "${EVAL_MODE_ARGS[@]}"

EVAL_DECODER=proof_constrained
if [ "$EVAL_FINAL_ONLY_COQ_CHECK" -eq 1 ]; then
  EVAL_DECODER=final_only_proof_constrained
fi

"$EVAL_PY" score_java_no_write.py \
  --task "$EVAL_TASK" --split test --output_tag "$EVAL_TAG" \
  --pass_at_k "$EVAL_BEAM_SIZE" --workers 64 --timeout "$EVAL_TIMEOUT" \
  --model_output_task "$EVAL_MODEL" --model_type last \
  --model_checkpoint_path "$EVAL_CHECKPOINT" \
  --model_checkpoint_sha256 "$EVAL_SHA" \
  --decoder "$EVAL_DECODER" --beam_size "$EVAL_BEAM_SIZE" \
  --length_penalty "$EVAL_LENGTH_PENALTY" \
  --generation_max_length "$EVAL_EFFECTIVE_MAX_LEN" \
  --candidate_multiplier "$EVAL_CANDIDATE_MULTIPLIER" \
  --benchmark_source_path "Utils/data/${EVAL_TASK}/test.pkl" \
  --json_out "$EVAL_SCORE"

"$EVAL_PY" - "$EVAL_SCORE" "$EVAL_BEAM_SIZE" <<'PY'
import json
import sys

score = json.load(open(sys.argv[1]))
beam_size = int(sys.argv[2])
required = ["pass1", "problems", "missing_problem_outputs"]
if beam_size >= 10:
    required.append("pass10")
missing = [key for key in required if key not in score]
if missing:
    raise SystemExit(f"score artifact lacks required fields: {missing}")
if score["missing_problem_outputs"]:
    raise SystemExit(
        f"missing problem outputs: {score['missing_problem_outputs']}"
    )
print(
    {
        "pass@1": score["pass1"],
        f"pass@{beam_size}": score.get("pass10", score["pass1"]),
        "total": score["problems"],
        "score_json": sys.argv[1],
    }
)
PY
