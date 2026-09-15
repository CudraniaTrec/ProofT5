#!/usr/bin/env bash
# RQ3 realignment stage 3: iterative compiler repair over the new clean673 control.
set -euo pipefail
cd /data2/x/hzc/prooft5
/data2/x/hzc/.uv-envs/prooft5-t5gemma-py313/bin/python baselines/java_baselines/run_repair_from_initial.py \
  --initial_dir Utils/output/mbjp_original_test_t5gemma2_20260731_test_ans/rq3clean_mbjp_ordinary_matched_b10_merged_20260914 \
  --dataset_json t5_llm/data/java_mbjp_original_test_t5.json --dataset_split test \
  --score_task mbjp_original_test_t5gemma2_20260731 --score_split test \
  --output_tag rq3clean_mbjp_repairfromordinary_b10_r2_20260914 \
  --model Utils/models/t5gemma-2-1b-1b --tokenizer Utils/models/t5gemma-2-1b-1b \
  --model_family seq2seq --device cuda:0 --dtype bf16 --local_files_only \
  --candidates 10 --max_repair_rounds 2 --temperature 0.8 --top_p 0.95 --greedy_first \
  --seed 273567 > tmp/rq3clean_repairfromordinary_20260914.log 2>&1
echo "stage3 repair done"
