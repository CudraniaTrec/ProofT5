#!/usr/bin/env bash
# Evaluate an ordinary T5Gemma2 checkpoint on one frozen plain-format JSON file.

set -euo pipefail

if [ "$#" -ne 4 ]; then
  printf 'usage: %s CHECKPOINT_DIR DATASET_JSON EVAL_TASK OUTPUT_TAG\n' "$0" >&2
  exit 64
fi

CHECKPOINT="$1"
DATASET_JSON="$2"
EVAL_TASK="$3"
TAG="$4"
cd /data2/x/hzc/prooft5

PY=/data2/x/hzc/.uv-envs/prooft5-t5gemma-py313/bin/python
GPU="${JAVA_EXPANSION_PLAIN_EVAL_GPU:-0}"
MAX_USED_MIB="${JAVA_EXPANSION_PLAIN_EVAL_MAX_USED_MIB:-1024}"
TOKENIZER_PATH="${JAVA_EXPANSION_PLAIN_TOKENIZER_PATH:-$CHECKPOINT}"
TIMEOUT="${CLEAN_JAVA_SCORE_TIMEOUT:-10}"
GENERATE_ALL_ROWS="${JAVA_EXPANSION_PLAIN_GENERATE_ALL_ROWS:-0}"
TARGET_MODE="${JAVA_EXPANSION_PLAIN_TARGET_MODE:-full}"
OUTPUT="Utils/output/${EVAL_TASK}_test_ans/${TAG}"
SCORE="tmp/${TAG}_score_timeout${TIMEOUT}.json"
DATA_ROOT="Utils/data/${EVAL_TASK}"

if ! [[ "$EVAL_TASK" =~ ^[A-Za-z0-9._-]+$ && "$TAG" =~ ^[A-Za-z0-9._-]+$ ]]; then
  printf 'evaluation task and tag must be filename-safe\n' >&2
  exit 64
fi
if [[ "$GENERATE_ALL_ROWS" != "0" && "$GENERATE_ALL_ROWS" != "1" ]]; then
  printf 'JAVA_EXPANSION_PLAIN_GENERATE_ALL_ROWS must be 0 or 1\n' >&2
  exit 64
fi
if [[ "$TARGET_MODE" != "full" && "$TARGET_MODE" != "solution" ]]; then
  printf 'JAVA_EXPANSION_PLAIN_TARGET_MODE must be full or solution\n' >&2
  exit 64
fi
for path in "$CHECKPOINT/config.json" "$DATASET_JSON"; do
  [ -f "$path" ] || { printf 'missing input: %s\n' "$path" >&2; exit 66; }
done
if [ ! -e "$TOKENIZER_PATH" ]; then
  printf 'missing tokenizer path: %s\n' "$TOKENIZER_PATH" >&2
  exit 66
fi
for path in "$DATA_ROOT" "$OUTPUT" "$SCORE"; do
  [ ! -e "$path" ] || { printf 'refusing to overwrite %s\n' "$path" >&2; exit 73; }
done
USED="$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i "$GPU" | tr -d ' ')"
[ "$USED" -lt "$MAX_USED_MIB" ] || { printf 'GPU %s is occupied (%s MiB)\n' "$GPU" "$USED" >&2; exit 75; }

MANIFEST_SHA="$({
  find "$CHECKPOINT" -maxdepth 1 -type f -printf '%f\0' | sort -z | \
    while IFS= read -r -d '' name; do
      file="$CHECKPOINT/$name"
      printf '%s %s ' "$name" "$(stat -c '%s' "$file")"
      sha256sum "$file" | awk '{print $1}'
    done
} | sha256sum | awk '{print $1}')"

GENERATE_ALL_ROWS_ARG=()
if [ "$GENERATE_ALL_ROWS" = "1" ]; then
  GENERATE_ALL_ROWS_ARG=(--generate_all_rows)
fi
PREFIX_ARGS=()
if [ "$TARGET_MODE" = "solution" ]; then
  PREFIX_ARGS=(--preserve_input_prefix)
fi

CUDA_VISIBLE_DEVICES="$GPU" TOKENIZERS_PARALLELISM=false \
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
"$PY" -u t5_llm/finetune_t5gemma2.py \
  --dataset mbjp --dataset_file "$DATASET_JSON" --task_name "$EVAL_TASK" \
  --generate_only "${GENERATE_ALL_ROWS_ARG[@]}" \
  --target_mode "$TARGET_MODE" "${PREFIX_ARGS[@]}" \
  --checkpoint_path "$CHECKPOINT" --tokenizer_path "$TOKENIZER_PATH" \
  --output_subdir "$TAG" \
  --cuda 0 --eval_batch_size 1 --topk 10 --generation_max_length 1024 \
  --generation_length_penalty 1.0 \
  --bf16 --no_swanlab --local_files_only

"$PY" score_java_no_write.py \
  --task "$EVAL_TASK" --split test --output_tag "$TAG" \
  --pass_at_k 10 --workers 64 --timeout "$TIMEOUT" \
  --model_output_task "$(basename "$CHECKPOINT")" --model_type hf_directory \
  --model_checkpoint_path "$CHECKPOINT" \
  --model_checkpoint_sha256 "$MANIFEST_SHA" \
  --decoder hf_beam --beam_size 10 --length_penalty 1.0 \
  --generation_max_length 1024 \
  --benchmark_source_path "$DATASET_JSON" --json_out "$SCORE"

"$PY" - "$SCORE" <<'PY'
import json, sys
score = json.load(open(sys.argv[1]))
if score.get("missing_problem_outputs"):
    raise SystemExit(f"missing outputs: {score['missing_problem_outputs']}")
print({"pass@1": score["pass1"], "pass@10": score["pass10"], "total": score["problems"]})
PY
