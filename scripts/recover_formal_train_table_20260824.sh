#!/usr/bin/env bash
set -euo pipefail

# Recover the paper-table evaluation chain after the original orchestration
# shells exited while their generation children survived.  This script never
# restarts the active HumanEval/GFG generators.  It waits for their complete
# problem metadata, performs sparse-aware audited merges, scores them, and
# only then launches the already-planned MBJP Coq/CoqView train evaluations.

cd /data2/x/hzc/prooft5

PY=/data2/x/hzc/.uv-envs/prooft5-t5gemma-py313/bin/python
ACC=/data2/x/hzc/.uv-envs/prooft5-t5gemma-py313/bin/accelerate
ACC_CONFIG=tmp/acc_config_ddp_bf16.yaml

HE_TASK=humaneval_clean65_train_eval_coqview_20260823
HE_MODEL=mbjpcoqview_clean673_from_java_clean30_fullseq_20260810_java_fullseq_b1_lr1em6_pass10_20260810_160322
HE_ROOT=Utils/output/${HE_TASK}_test_ans
HE_MERGED=formal_train_he65_coqview_lpt4_merged_20260823
HE_SCORE=tmp/formal_train_he65_coqview_lpt4_merged_20260823_score_timeout10.json
HE_CKPT=Utils/models/Model${HE_MODEL}/last_model.ckpt

GFG_TASK=gfg_v14_train414_eval_t5gemma2_20260823
GFG_MODEL=java_mbjp_transcoder_gfg_parent_safe2164_v14_coq_selected_20260820
GFG_ROOT=Utils/output/${GFG_TASK}_test_ans
GFG_MERGED=formal_train_gfg414_coq_lpt8_merged_20260823
GFG_SCORE=tmp/formal_train_gfg414_coq_lpt8_merged_20260823_score_timeout10.json
GFG_CKPT=Utils/models/Model${GFG_MODEL}/last_model.ckpt

he_tags=(
  formal_train_he65_coqview_lpt4_group0_w16_20260823
  formal_train_he65_coqview_lpt4_group1_w16_20260823
  formal_train_he65_coqview_lpt4_group2_w16_20260823
  formal_train_he65_coqview_lpt4_group3_w16_20260823
)

gfg_old_tags=(
  formal_train_gfg414_coq_lpt8_shard0_w64_20260823
  formal_train_gfg414_coq_lpt8_shard1_w64_20260823
  formal_train_gfg414_coq_lpt8_shard2_w32_20260823
  formal_train_gfg414_coq_lpt8_shard3_w32_20260823
  formal_train_gfg414_coq_lpt8_shard4retry_w32_20260823
  formal_train_gfg414_coq_lpt8_shard5_w32_20260823
  formal_train_gfg414_coq_lpt8_shard6_w32_20260823
  formal_train_gfg414_coq_lpt8_shard7_w32_20260823
)
gfg_new_tags=()
for i in $(seq 0 15); do
  gfg_new_tags+=("formal_train_gfg414_coq_reshard16_shard${i}_w20_20260823")
done

metadata_count() {
  local root=$1
  shift
  "$PY" - "$root" "$@" <<'PY'
import re
import sys
from pathlib import Path

root = Path(sys.argv[1])
ids = {}
for tag in sys.argv[2:]:
    for path in (root / tag).glob("*_beam_scores.json"):
        match = re.fullmatch(r"(\d+)_beam_scores\.json", path.name)
        if not match:
            raise SystemExit(f"unexpected metadata filename: {path}")
        ids.setdefault(int(match.group(1)), []).append(tag)
duplicates = {key: value for key, value in ids.items() if len(value) > 1}
if duplicates:
    raise SystemExit(f"duplicate problem IDs across sources: {duplicates}")
print(len(ids))
PY
}

recover_he() {
  if [[ -f "$HE_SCORE" ]]; then
    echo "$(date -u +%FT%TZ) HECV score already exists"
    return
  fi
  while :; do
    count=$(metadata_count "$HE_ROOT" "${he_tags[@]}")
    echo "$(date -u +%FT%TZ) waiting HECV metadata=${count}/65"
    [[ "$count" -eq 65 ]] && break
    sleep 30
  done

  args=()
  for tag in "${he_tags[@]}"; do
    args+=(--source "$HE_ROOT/$tag")
  done
  [[ ! -e "$HE_ROOT/$HE_MERGED" ]]
  "$PY" scripts/merge_candidate_output_shards.py \
    "${args[@]}" \
    --output "$HE_ROOT/$HE_MERGED" \
    --expected-size 65 \
    --candidates 10 \
    --allow-missing-candidates

  sha=$(sha256sum "$HE_CKPT" | awk '{print $1}')
  "$PY" score_java_no_write.py \
    --task "$HE_TASK" \
    --split test \
    --output_tag "$HE_MERGED" \
    --pass_at_k 10 \
    --workers 16 \
    --timeout 10 \
    --model_output_task "$HE_MODEL" \
    --model_type last \
    --model_checkpoint_path "$HE_CKPT" \
    --model_checkpoint_sha256 "$sha" \
    --decoder proof_constrained \
    --beam_size 10 \
    --length_penalty 0.1 \
    --generation_max_length 564 \
    --candidate_multiplier 20 \
    --benchmark_source_path "Utils/data/$HE_TASK/test.pkl" \
    --json_out "$HE_SCORE"
  echo "$(date -u +%FT%TZ) HECV score complete"
}

recover_gfg() {
  if [[ -f "$GFG_SCORE" ]]; then
    echo "$(date -u +%FT%TZ) GFG score already exists"
    return
  fi
  all_tags=("${gfg_old_tags[@]}" "${gfg_new_tags[@]}")
  while :; do
    count=$(metadata_count "$GFG_ROOT" "${all_tags[@]}")
    echo "$(date -u +%FT%TZ) waiting GFG metadata=${count}/414"
    [[ "$count" -eq 414 ]] && break
    sleep 30
  done

  args=()
  for tag in "${all_tags[@]}"; do
    args+=(--source "$GFG_ROOT/$tag")
  done
  [[ ! -e "$GFG_ROOT/$GFG_MERGED" ]]
  "$PY" scripts/merge_candidate_output_shards.py \
    "${args[@]}" \
    --output "$GFG_ROOT/$GFG_MERGED" \
    --expected-size 414 \
    --candidates 10 \
    --allow-missing-candidates

  sha=$(sha256sum "$GFG_CKPT" | awk '{print $1}')
  "$PY" score_java_no_write.py \
    --task "$GFG_TASK" \
    --split test \
    --output_tag "$GFG_MERGED" \
    --pass_at_k 10 \
    --workers 64 \
    --timeout 10 \
    --model_output_task "$GFG_MODEL" \
    --model_type last \
    --model_checkpoint_path "$GFG_CKPT" \
    --model_checkpoint_sha256 "$sha" \
    --decoder proof_constrained \
    --beam_size 10 \
    --length_penalty 0.1 \
    --generation_max_length 555 \
    --candidate_multiplier 20 \
    --benchmark_source_path "Utils/data/$GFG_TASK/test.pkl" \
    --json_out "$GFG_SCORE"
  echo "$(date -u +%FT%TZ) GFG score complete"
}

launch_mbjp() {
  local coq_score=tmp/formal_train_mbjp608_coq_lpt8_merged_20260823_score_timeout10.json
  local cv_score=tmp/formal_train_mbjp608_coqview_lpt8_merged_20260823_score_timeout10.json
  if [[ -f "$coq_score" && -f "$cv_score" ]]; then
    echo "$(date -u +%FT%TZ) MBJP scores already exist"
    return
  fi

  local coq_task=mbjp_clean608_train_eval_t5gemma2_20260823
  local cv_task=mbjp_clean608_train_eval_coqview_20260823
  local coq_model=mbjp_humaneval_half_train_t5gemma2_20260731_clean673_noleak_formal30_8gpu_b5_lr1em5_20260810
  local cv_model=mbjpcoqview_clean673_from_java_clean30_fullseq_20260810_java_fullseq_b1_lr1em6_pass10_20260810_160322
  local coq_root=Utils/output/${coq_task}_test_ans
  local cv_root=Utils/output/${cv_task}_test_ans
  local coq_ckpt=Utils/models/Model${coq_model}/last_model.ckpt
  local cv_ckpt=Utils/models/Model${cv_model}/last_model.ckpt
  local gpus=(0 1 6 7)
  local pids=()
  local coq_tags=()
  local cv_tags=()

  launch_one() {
    local task=$1
    local model=$2
    local tag=$3
    local gpu=$4
    local port=$5
    local indices=$6
    local force=$7
    local extra=()
    [[ "$force" -eq 1 ]] && extra+=(--force_coq_decoder)
    CUDA_VISIBLE_DEVICES="$gpu" \
      OMP_NUM_THREADS=8 \
      MKL_NUM_THREADS=8 \
      OPENBLAS_NUM_THREADS=8 \
      NUMEXPR_NUM_THREADS=8 \
      TOKENIZERS_PARALLELISM=false \
      PROOFT5_DISTRIBUTED_TIMEOUT_MINUTES=720 \
      TORCH_NCCL_HEARTBEAT_TIMEOUT_SEC=7200 \
      TORCH_NCCL_ASYNC_ERROR_HANDLING=1 \
      PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
      "$ACC" launch \
        --config_file "$ACC_CONFIG" \
        --num_processes 1 \
        --main_process_port "$port" \
        run.py \
        --eval \
        --task "$task" \
        --model_output_task "$model" \
        --model_type last \
        --eval_split test \
        --output_tag "$tag" \
        --beam_size 10 \
        --length_penalty 0.1 \
        --coq_candidate_multiplier 20 \
        --coq_workers 24 \
        --coq_timeout 20 \
        --runtime_dir "tmp/runtime_state/$tag" \
        --batch_size_eval 1 \
        --eval_num_workers 0 \
        --disable_tqdm \
        --no_swanlab \
        --eval_indices "$indices" \
        "${extra[@]}" \
        > "tmp/$tag.log" 2>&1 &
    pids+=("$!")
  }

  for i in $(seq 0 7); do
    indices=$("$PY" - "$i" <<'PY'
import json
import sys
print(json.load(open("tmp/formal_train_mbjp608_coq_lpt8_20260823.json"))["shards"][int(sys.argv[1])]["indices_csv"])
PY
)
    tag="formal_train_mbjp608_coq_lpt8_shard${i}_w24_20260823"
    coq_tags+=("$tag")
    if [[ -e "$coq_root/$tag" ]]; then
      echo "$(date -u +%FT%TZ) reusing existing MBJP Coq tag=$tag"
    else
      launch_one "$coq_task" "$coq_model" "$tag" "${gpus[$((i % 4))]}" "$((31100 + i))" "$indices" 1
    fi
  done
  for i in $(seq 0 7); do
    indices=$("$PY" - "$i" <<'PY'
import json
import sys
print(json.load(open("tmp/formal_train_mbjp608_coqview_lpt8_20260823.json"))["shards"][int(sys.argv[1])]["indices_csv"])
PY
)
    tag="formal_train_mbjp608_coqview_lpt8_shard${i}_w24_20260823"
    cv_tags+=("$tag")
    if [[ -e "$cv_root/$tag" ]]; then
      echo "$(date -u +%FT%TZ) reusing existing MBJP CoqView tag=$tag"
    else
      launch_one "$cv_task" "$cv_model" "$tag" "${gpus[$((i % 4))]}" "$((31108 + i))" "$indices" 0
    fi
  done
  echo "$(date -u +%FT%TZ) launched MBJP pids=${pids[*]}"

  while :; do
    coq_count=$(metadata_count "$coq_root" "${coq_tags[@]}")
    cv_count=$(metadata_count "$cv_root" "${cv_tags[@]}")
    echo "$(date -u +%FT%TZ) waiting MBJP Coq=${coq_count}/608 CoqView=${cv_count}/608"
    [[ "$coq_count" -eq 608 && "$cv_count" -eq 608 ]] && break
    sleep 30
  done
  for pid in "${pids[@]}"; do
    wait "$pid" || true
  done

  merge_mbjp() {
    local task=$1
    local model=$2
    local root=$3
    local merged=$4
    local score=$5
    local ckpt=$6
    shift 6
    local tags=("$@")
    local args=()
    for tag in "${tags[@]}"; do
      args+=(--source "$root/$tag")
    done
    [[ ! -e "$root/$merged" ]]
    "$PY" scripts/merge_candidate_output_shards.py \
      "${args[@]}" \
      --output "$root/$merged" \
      --expected-size 608 \
      --candidates 10 \
      --allow-missing-candidates
    sha=$(sha256sum "$ckpt" | awk '{print $1}')
    "$PY" score_java_no_write.py \
      --task "$task" \
      --split test \
      --output_tag "$merged" \
      --pass_at_k 10 \
      --workers 64 \
      --timeout 10 \
      --model_output_task "$model" \
      --model_type last \
      --model_checkpoint_path "$ckpt" \
      --model_checkpoint_sha256 "$sha" \
      --decoder proof_constrained \
      --beam_size 10 \
      --length_penalty 0.1 \
      --generation_max_length 564 \
      --candidate_multiplier 20 \
      --benchmark_source_path "Utils/data/$task/test.pkl" \
      --json_out "$score"
  }

  merge_mbjp \
    "$coq_task" "$coq_model" "$coq_root" \
    formal_train_mbjp608_coq_lpt8_merged_20260823 "$coq_score" "$coq_ckpt" \
    "${coq_tags[@]}"
  merge_mbjp \
    "$cv_task" "$cv_model" "$cv_root" \
    formal_train_mbjp608_coqview_lpt8_merged_20260823 "$cv_score" "$cv_ckpt" \
    "${cv_tags[@]}"
  echo "$(date -u +%FT%TZ) MBJP scores complete"
}

recover_he &
he_pid=$!
recover_gfg &
gfg_pid=$!
wait "$he_pid"
wait "$gfg_pid"
launch_mbjp
