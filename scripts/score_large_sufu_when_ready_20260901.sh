#!/usr/bin/env bash
# Score the two sharded SuFu F3 generations once all 58 candidates exist.
set -euo pipefail
ROOT=/data2/x/hzc/prooft5
ART=$ROOT/artifacts/major_revision_decoder_only_multibenchmark_20260828
PY=/data2/x/hzc/.uv-envs/prooft5-t5gemma-py313/bin/python
base=$ROOT/Utils/output/sufu_original_test_t5gemma2_20260731_test_ans
while [ "$(find "$base/qwen3_32b_sufu_f3_20260901" -maxdepth 1 -name '*.txt' | wc -l)" -lt 58 ] || \
      [ "$(find "$base/olmo3_1125_32b_sufu_f3_20260901" -maxdepth 1 -name '*.txt' | wc -l)" -lt 58 ]; do
  sleep 15
done
sleep 5
"$PY" "$ROOT/score_sufu_no_write.py" --task sufu_original_test_t5gemma2_20260731 --split test \
  --output_tag qwen3_32b_sufu_f3_20260901 --pass_at_k 1 \
  --model_output_task qwen3_32b_sufu_f3_20260901 --model_type qwen3-32b \
  --json_out "$ART/qwen3_32b_sufu_f3_score.json"
"$PY" "$ROOT/score_sufu_no_write.py" --task sufu_original_test_t5gemma2_20260731 --split test \
  --output_tag olmo3_1125_32b_sufu_f3_20260901 --pass_at_k 1 \
  --model_output_task olmo3_1125_32b_sufu_f3_20260901 --model_type olmo3-1125-32b \
  --json_out "$ART/olmo3_1125_32b_sufu_f3_score.json"
