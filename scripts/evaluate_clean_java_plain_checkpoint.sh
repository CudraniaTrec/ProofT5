#!/usr/bin/env bash
# Generate and functionally score one ordinary T5Gemma2 Java checkpoint.
#
# Usage:
#   scripts/evaluate_clean_java_plain_checkpoint.sh \
#     CHECKPOINT_DIR java_mbjp_test|java_humaneval_test OUTPUT_TAG

set -euo pipefail

if [ "$#" -ne 3 ]; then
  printf 'usage: %s CHECKPOINT_DIR java_mbjp_test|java_humaneval_test OUTPUT_TAG\n' \
    "$0" >&2
  exit 64
fi

PLAIN_CHECKPOINT="$1"
PLAIN_DATASET="$2"
PLAIN_TAG="$3"
case "$PLAIN_DATASET" in
  java_mbjp_test|java_humaneval_test) ;;
  *) printf 'unsupported Java evaluation dataset: %s\n' "$PLAIN_DATASET" >&2; exit 64 ;;
esac
if ! [[ "$PLAIN_TAG" =~ ^[A-Za-z0-9._-]+$ ]]; then
  printf 'output tag must be filename-safe\n' >&2
  exit 64
fi

cd /data2/x/hzc/prooft5

PLAIN_PY=/data2/x/hzc/.uv-envs/prooft5-t5gemma-py313/bin/python
PLAIN_GPU="${CLEAN_JAVA_PLAIN_EVAL_GPU:-0}"
PLAIN_TIMEOUT="${CLEAN_JAVA_SCORE_TIMEOUT:-10}"
PLAIN_EVAL_TASK="${PLAIN_TAG}_${PLAIN_DATASET}"
PLAIN_DATA_ROOT="Utils/data/${PLAIN_EVAL_TASK}"
PLAIN_OUTPUT="Utils/output/${PLAIN_EVAL_TASK}_test_ans/${PLAIN_TAG}"
PLAIN_SCORE="tmp/${PLAIN_TAG}_score_timeout${PLAIN_TIMEOUT}.json"

if [ ! -d "$PLAIN_CHECKPOINT" ] || [ ! -f "$PLAIN_CHECKPOINT/config.json" ]; then
  printf 'ordinary-model checkpoint directory is invalid: %s\n' \
    "$PLAIN_CHECKPOINT" >&2
  exit 66
fi
for path in "$PLAIN_DATA_ROOT" "$PLAIN_OUTPUT" "$PLAIN_SCORE"; do
  if [ -e "$path" ]; then
    printf 'refusing to overwrite evaluation artifact: %s\n' "$path" >&2
    exit 73
  fi
done

PLAIN_USED="$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i "$PLAIN_GPU" | tr -d ' ')"
if [ "$PLAIN_USED" -ge 1024 ]; then
  printf 'GPU %s is occupied (%s MiB); no evaluation artifact was created\n' \
    "$PLAIN_GPU" "$PLAIN_USED" >&2
  exit 75
fi

# Hash file names, file sizes, and file content hashes so sharded and unsharded
# Hugging Face checkpoints have one stable provenance identifier.
PLAIN_SHA="$({
  find "$PLAIN_CHECKPOINT" -maxdepth 1 -type f -printf '%f\0' | sort -z | \
    while IFS= read -r -d '' name; do
      file="$PLAIN_CHECKPOINT/$name"
      printf '%s %s ' "$name" "$(stat -c '%s' "$file")"
      sha256sum "$file" | awk '{print $1}'
    done
} | sha256sum | awk '{print $1}')"
printf '[%s] dataset=%s checkpoint=%s checkpoint_manifest_sha256=%s\n' \
  "$(date -Iseconds)" "$PLAIN_DATASET" "$PLAIN_CHECKPOINT" "$PLAIN_SHA"

CUDA_VISIBLE_DEVICES="$PLAIN_GPU" \
TOKENIZERS_PARALLELISM=false \
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
"$PLAIN_PY" -u t5_llm/finetune_t5gemma2.py \
  --dataset "$PLAIN_DATASET" --task_name "$PLAIN_EVAL_TASK" \
  --generate_only --checkpoint_path "$PLAIN_CHECKPOINT" \
  --output_subdir "$PLAIN_TAG" --cuda 0 --eval_batch_size 1 --topk 10 \
  --generation_max_length 1024 --bf16 --no_swanlab --local_files_only

"$PLAIN_PY" score_java_no_write.py \
  --task "$PLAIN_EVAL_TASK" --split test --output_tag "$PLAIN_TAG" \
  --pass_at_k 10 --workers 64 --timeout "$PLAIN_TIMEOUT" \
  --model_output_task "$(basename "$PLAIN_CHECKPOINT")" \
  --model_type hf_directory --model_checkpoint_path "$PLAIN_CHECKPOINT" \
  --model_checkpoint_sha256 "$PLAIN_SHA" --json_out "$PLAIN_SCORE"

"$PLAIN_PY" - "$PLAIN_SCORE" <<'PY'
import json
import sys

score = json.load(open(sys.argv[1]))
required = ("pass1", "pass10", "problems", "missing_problem_outputs")
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
        "pass@10": score["pass10"],
        "total": score["problems"],
        "score_json": sys.argv[1],
    }
)
PY
