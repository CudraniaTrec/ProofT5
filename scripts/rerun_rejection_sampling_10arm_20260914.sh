#!/bin/bash
# Extend the frozen 4-arm MBJP rejection sampling to 10 arms (100 candidates).
# Mirrors the frozen protocol exactly: same model, sampling params, seeds +1000/arm.
set -euo pipefail
cd /data2/x/hzc/prooft5
OUTROOT=Utils/output/mbjp_original_test_t5gemma2_20260731_test_ans
IDX=2,24,27,55,57,64
MODEL=t5_llm/models/paper_comparison_20260731/t5gemma2-2b_mbjp
for r in 5 6 7 8 9 10; do
  SEED=$((272567 + r * 1000))
  TAG=paperrecover_mbjp_rs_round${r}_b10_20260914
  if [ -f "$OUTROOT/$TAG/baseline_manifest.json" ]; then echo "skip round$r"; continue; fi
  /data2/x/hzc/.uv-envs/prooft5-t5gemma-py313/bin/python -m baselines.java_baselines.run_repilot \
    --model $MODEL --model_family seq2seq --tokenizer Utils/models/t5gemma-2-1b-1b \
    --dataset_json t5_llm/data/java_mbjp_original_test_t5.json --dataset_split test \
    --score_task mbjp_original_test_t5gemma2_20260731 --score_split test \
    --output_tag $TAG --device cuda:0 --dtype bf16 --local_files_only \
    --candidates 10 --max_input_tokens 1024 --max_new_tokens 1024 \
    --temperature 0.8 --top_k 50 --top_p 0.95 --greedy_first \
    --decoder_control_no_jdt --seed $SEED --indices $IDX \
    > tmp/rs_round${r}_20260914.log 2>&1
  echo "round$r done"
done
# Assemble 10-arm candidate set (control + 9 resample arms)
/data2/x/hzc/.uv-envs/prooft5-t5gemma-py313/bin/python -m baselines.java_baselines.run_rejection_sampling_assembly \
  --control_dir $OUTROOT/paperrecover_mbjp_ordinary_matched_b10_merged_20260825 \
  --resample_dirs "$OUTROOT/paperrecover_mbjp_rs_round2_b10_20260827,$OUTROOT/paperrecover_mbjp_rs_round3_b10_20260827,$OUTROOT/paperrecover_mbjp_rs_round4_b10_20260827,$OUTROOT/paperrecover_mbjp_rs_round5_b10_20260914,$OUTROOT/paperrecover_mbjp_rs_round6_b10_20260914,$OUTROOT/paperrecover_mbjp_rs_round7_b10_20260914,$OUTROOT/paperrecover_mbjp_rs_round8_b10_20260914,$OUTROOT/paperrecover_mbjp_rs_round9_b10_20260914,$OUTROOT/paperrecover_mbjp_rs_round10_b10_20260914" \
  --output_dir $OUTROOT/paperrecover_mbjp_rejectionsampling10arm_b10_20260914 \
  --expected_problems 67 --expected_candidates 10 --max_arms_per_problem 10 \
  > tmp/rs10arm_assembly_20260914.log 2>&1
echo "assembly done"
# Score with the frozen scorer (timeout 10)
/data2/x/hzc/.uv-envs/prooft5-t5gemma-py313/bin/python score_java_no_write.py --task mbjp_original_test_t5gemma2_20260731 --split test \
  --output_tag paperrecover_mbjp_rejectionsampling10arm_b10_20260914 --timeout 10 \
  > tmp/rs10arm_score_20260914.log 2>&1
/data2/x/hzc/.uv-envs/prooft5-t5gemma-py313/bin/python - <<'PY'
import json
d=json.load(open('tmp/paperrecover_mbjp_rejectionsampling10arm_b10_20260914_score_timeout10.json'))
print('pass1',d['pass1'],'pass10',d['pass10'],'CER',d.get('compile_error_rate'),'missing',d.get('missing'))
m=json.load(open('Utils/output/mbjp_original_test_t5gemma2_20260731_test_ans/paperrecover_mbjp_rejectionsampling10arm_b10_20260914/baseline_manifest.json'))
print('kept_from_arm',m['kept_from_arm'],'total_draws',m['total_draws'])
PY
echo ALL_DONE
