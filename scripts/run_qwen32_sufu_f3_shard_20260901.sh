#!/usr/bin/env bash
# Generate a disjoint shard of Qwen3-32B SuFu three-shot candidates.
# Existing files are resumed and never overwritten.
set -euo pipefail
if [ "$#" -ne 2 ]; then
  echo "usage: $0 GPU INDICES" >&2
  exit 2
fi
GPU=$1
INDICES=$2
ROOT=/data2/x/hzc/prooft5
PY=/data2/x/hzc/.uv-envs/prooft5-t5gemma-py313/bin/python
MODEL=/data2/x/hzc/hf_models/Qwen3-32B
ART=$ROOT/artifacts/major_revision_decoder_only_multibenchmark_20260828
FS=$ART/inputs/sufu_few_shot_train_only_noio_notest_20260902.json
DATA=$ROOT/t5_llm/data/sufu_original_test_t5.json
export CUDA_VISIBLE_DEVICES="$GPU"
exec "$PY" "$ROOT/baselines/java_baselines/run_decoder_only_sufu.py" \
  --backend hf --model "$MODEL" --model_family causal --dtype bf16 --device cuda \
  --local_files_only --candidates 1 --greedy_first --max_tokens 1024 \
  --temperature 0.8 --top_p 0.95 --seed 273567 --no_chat_template \
  --prompt_mode full_source --guidance_profile high_information \
  --few_shot_k 3 --few_shot_dataset "$FS" \
  --few_shot_ids incre-tests-synduce-constraints-sortedlist-parallel_max2,incre-tests-synduce-zipper-list_sum,incre-tests-synduce-constraints-all_positive-sndmax \
  --dataset_json "$DATA" --score_task sufu_original_test_t5gemma2_20260731 \
  --score_split test --output_tag qwen3_32b_sufu_f3_20260901 --resume \
  --indices "$INDICES"
