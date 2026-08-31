#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 3 ]; then
  echo "usage: $0 <ordinary|syncode|repilot|iterative> <mbjp|humaneval|gfg> <output_tag> [runner args...]" >&2
  exit 2
fi

METHOD="$1"
BENCHMARK="$2"
OUTPUT_TAG="$3"
shift 3

PROJECT_PYTHON="${PROOFT5_PYTHON:-/data2/x/hzc/.uv-envs/prooft5-t5gemma-py313/bin/python}"
SYNCODE_PYTHON="${PROOFT5_SYNCODE_T5GEMMA_PYTHON:-/data2/x/hzc/.uv-envs/prooft5-syncode-t5gemma-py312/bin/python}"
TOKENIZER="Utils/models/t5gemma-2-1b-1b"
GPU="${PROOFT5_BASELINE_GPU:-0}"
CANDIDATES="${PROOFT5_BASELINE_CANDIDATES:-10}"
MAX_TOKENS="${PROOFT5_BASELINE_MAX_TOKENS:-1024}"
TEMPERATURE="${PROOFT5_BASELINE_TEMPERATURE:-0.8}"
SEED="${PROOFT5_BASELINE_SEED:-273567}"

case "$BENCHMARK" in
  mbjp)
    DATASET="t5_llm/data/java_mbjp_original_test_t5.json"
    SCORE_TASK="mbjp_original_test_t5gemma2_20260731"
    # Paper-row recovery checkpoint selected and archived on 2026-07-31 after
    # the exhaustive checkpoint audit.  Do not perform another test-set sweep.
    MODEL="${PROOFT5_MBJP_BASELINE_MODEL:-t5_llm/models/paper_comparison_20260731/t5gemma2-2b_mbjp}"
    ;;
  humaneval)
    DATASET="Utils/data/java_humaneval_v15_semanticsupport_plain_selected_test16_eval_20260822/test.pkl"
    SCORE_TASK="java_humaneval_mbjp_native_semanticsupport_split90_10_t5gemma2_20260822_v15"
    MODEL="t5_llm/models/t5gemma2-2b_java_mbjp_humaneval_semanticsupport1082_v15_plain_selected_20260822"
    ;;
  gfg)
    DATASET="Utils/data/java_transcoder_gfg_v13_mbjp_native_plain_stage2_test_eval_20260819/test.pkl"
    SCORE_TASK="java_transcoder_gfg_mbjp_native_prompt_split80_20_t5gemma2_20260819_v13"
    MODEL="t5_llm/models/t5gemma2-2b_java_mbjp_transcoder_gfg_mbjp_native_prompt2164_v13_exposure3_pair_frombase_stage2_selected_20260819"
    ;;
  *)
    echo "unknown benchmark: $BENCHMARK" >&2
    exit 2
    ;;
esac

COMMON=(
  --dataset_json "$DATASET"
  --score_task "$SCORE_TASK"
  --score_split test
  --output_tag "$OUTPUT_TAG"
  --model "$MODEL"
  --tokenizer "$TOKENIZER"
  --model_family seq2seq
  --device cuda:0
  --dtype bf16
  --local_files_only
  --candidates "$CANDIDATES"
  --seed "$SEED"
  --greedy_first
)

case "$METHOD" in
  ordinary)
    RUNNER="baselines/java_baselines/run_repilot.py"
    PYTHON="$PROJECT_PYTHON"
    METHOD_ARGS=(
      --max_new_tokens "$MAX_TOKENS"
      --temperature "$TEMPERATURE"
      --top_p 0.95
      --top_k 50
      --decoder_control_no_jdt
    )
    ;;
  syncode)
    RUNNER="baselines/java_baselines/run_syncode.py"
    PYTHON="$SYNCODE_PYTHON"
    METHOD_ARGS=(
      --max_new_tokens "$MAX_TOKENS"
      --candidate_timeout_seconds "${PROOFT5_SYNCODE_CANDIDATE_TIMEOUT:-240}"
      --temperature "$TEMPERATURE"
      --top_p 0.95
      --top_k 50
    )
    export OMP_NUM_THREADS="${PROOFT5_SYNCODE_CPU_THREADS:-1}"
    export MKL_NUM_THREADS="${PROOFT5_SYNCODE_CPU_THREADS:-1}"
    ;;
  repilot)
    RUNNER="baselines/java_baselines/run_repilot.py"
    PYTHON="$PROJECT_PYTHON"
    METHOD_ARGS=(
      --max_new_tokens "$MAX_TOKENS"
      --temperature "$TEMPERATURE"
      --top_p 0.95
      --top_k 50
    )
    ;;
  iterative)
    RUNNER="baselines/java_baselines/run_iterative_refinement.py"
    PYTHON="$PROJECT_PYTHON"
    METHOD_ARGS=(
      --backend hf
      --hf_seq2seq_initial_mode task_prefix
      --hf_seq2seq_prompt_mode last_user
      --max_repair_rounds 2
      --max_tokens_per_call "$MAX_TOKENS"
      --temperature "$TEMPERATURE"
      --top_p 0.95
    )
    ;;
  *)
    echo "unknown method: $METHOD" >&2
    exit 2
    ;;
esac

CUDA_VISIBLE_DEVICES="$GPU" exec "$PYTHON" "$RUNNER" "${COMMON[@]}" "${METHOD_ARGS[@]}" "$@"
