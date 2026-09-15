#!/bin/bash
# Build the minimal TOSEM paper artifact at /data2/x/hzc/prooft5/artifact.
# Copies only the frozen checkpoints/data backing reported paper rows.
# Provenance for each mapping: MODEL_TRAINING_INVENTORY.md, docs/experiments/*,
# docs/MAJOR_REVISION_FINAL_PACKAGE_20260824.md, results_final.csv.
set -euo pipefail
REPO=/data2/x/hzc/prooft5
OUT=$REPO/artifact
mkdir -p $OUT/{code,data,checkpoints}

# ---- code -------------------------------------------------------------
cd $REPO
cp run.py Model.py ModelT5Gemma2.py Dataset.py get_tokenizer.py trans_dsl_program.py \
   beamsearch.py beamsearch_coq.py beamsearch_sufu.py beamsearch_sufu_cd.py \
   beamsearch_cache.py beamsearch_dsl.py score_java_no_write.py score_sufu_no_write.py \
   acc_config.yaml requirements.txt requirements-t5gemma2.txt $OUT/code/
cp prepare_t5gemma2_*.py $OUT/code/ 2>/dev/null || true
# coq_model: source only; coq_code/mbjp (1.2T of per-task generated dirs) and
# datas/ (828M generated datasets) are excluded -- regenerable via Makefile.
mkdir -p $OUT/code/coq_model/coq_code
cp coq_model/*.py coq_model/*.json coq_model/Makefile coq_model/Makefile.coq \
   coq_model/Makefile.coq.conf coq_model/_CoqProject coq_model/README.md $OUT/code/coq_model/ 2>/dev/null || true
cp coq_model/coq_code/*.v coq_model/coq_code/*.vo coq_model/coq_code/*.vok \
   coq_model/coq_code/*.vos coq_model/coq_code/*.glob $OUT/code/coq_model/coq_code/ 2>/dev/null || true
cp -r coq_model/mxeval coq_model/myjavalang coq_model/pretrain $OUT/code/coq_model/
cp -r SuFu $OUT/code/SuFu
cp -r baselines/java_baselines $OUT/code/baselines

# ---- data -------------------------------------------------------------
mkdir -p $OUT/data/{sufu,mbjp,humaneval,gfg,opencoder}
cp -r Utils/data/sufucoq/* $OUT/data/sufu/
cp t5_llm/data/sufu_t5.json $OUT/data/sufu/plain_baseline.json
cp -r Utils/data/mbjpcoq/* $OUT/data/mbjp/
cp t5_llm/data/mbjp_t5.json $OUT/data/mbjp/plain_baseline.json
cp Utils/data/mbjp_humaneval_half_train_t5gemma2_20260731/train.pkl $OUT/data/mbjp/train_2b.pkl
cp Utils/data/mbjp_original_test_t5gemma2_20260731/test.pkl $OUT/data/mbjp/test_2b.pkl
cp -r Utils/data/java_humaneval_mbjp_native_semanticsupport_split90_10_t5gemma2_20260822_v15/* $OUT/data/humaneval/
cp -r Utils/data/java_transcoder_gfg_mbjp_native_prompt_split80_20_t5gemma2_20260819_v13/* $OUT/data/gfg/
cp Utils/data/java_humaneval_v15_transcoder_v13_dual1082_t5gemma2_20260823/train.pkl $OUT/data/humaneval/dual1082_train.pkl 2>/dev/null || true
cp -r Utils/data/pretrain_t5gemma2_2b_retok/* $OUT/data/opencoder/

# ---- checkpoints ------------------------------------------------------
# 220M TyFlow MBJP (11.94/28.36/7.94/3.52, results_final.csv mbjp_coqview)
mkdir -p $OUT/checkpoints/tyflow-220m-mbjp
cp Utils/models/Modelmbjpcoqview/2025-06-20_16-57-57/epoch80_model.ckpt $OUT/checkpoints/tyflow-220m-mbjp/
# 2B TyFlow SuFu (36.21/48.28/5.53/0.00; recovered 2026-09-15, see
# artifacts/sufu_2b_rerun_20260915/README.md)
mkdir -p $OUT/checkpoints/tyflow-2b-sufu
cp Utils/models/Modelsufu_original_synthetic_half_train_t5gemma2_20260731_complete281_formal100_8gpu_b5_lr5em5_20260731_105207/last_model.ckpt $OUT/checkpoints/tyflow-2b-sufu/
# 2B TyFlow MBJP (25.37/43.28)
mkdir -p $OUT/checkpoints/tyflow-2b-mbjp
cp Utils/models/Modelmbjp_humaneval_half_train_t5gemma2_20260731_clean673_noleak_formal30_8gpu_b5_lr1em5_20260810/last_model.ckpt $OUT/checkpoints/tyflow-2b-mbjp/
# 2B TyFlow Java dual (HE 50.00/56.25, GFG 30.10/46.60)
mkdir -p $OUT/checkpoints/tyflow-2b-java
cp Utils/models/Modeljoint23_dual_hegfg_from_heonly_lr2e6_p5_20260823/last_model.ckpt $OUT/checkpoints/tyflow-2b-java/
# OpenCoder cold-start pretrain
mkdir -p $OUT/checkpoints/tyflow-2b-pretrain
cp Utils/models/Modelpretrain_t5gemma2_2b_retok_corrected_formal5pass_lr1em5_8gpu_b5_20260715_1412/last_model.ckpt $OUT/checkpoints/tyflow-2b-pretrain/
# 220M baselines
cp -r t5_llm/models/codet5-base_sufu/2025-06-29_23-21-14/epoch_160 $OUT/checkpoints/baseline-220m-sufu
cp -r t5_llm/models/codet5-base_mbjp/2025-07-02_15-48-24/epoch_50 $OUT/checkpoints/baseline-220m-mbjp
# 2B baselines
cp -r t5_llm/models/paper_comparison_20260731/t5gemma2-2b_sufu $OUT/checkpoints/baseline-2b-sufu
cp -r t5_llm/models/paper_comparison_20260731/t5gemma2-2b_mbjp $OUT/checkpoints/baseline-2b-mbjp
cp -r t5_llm/models/t5gemma2-2b_bBfinal_union_lr1e5_20260909/bBfinal_20260909/epoch_20 $OUT/checkpoints/baseline-2b-humaneval
cp -r t5_llm/models/t5gemma2-2b_gBfinal_mbjpgfg1022_lr1e5_20260910/gBfinal_20260910/epoch_15 $OUT/checkpoints/baseline-2b-gfg
# RQ4 variants (mapping from results_final.csv; note dir-name swap across benchmarks)
cp -r t5_llm/models/codet5-base_sufu_proofcode/2025-09-15_10-24-17/epoch_90 $OUT/checkpoints/rq4-sufu-type-first
cp -r t5_llm/models/codet5-base_sufu_codeproof/2025-09-22_17-20-27/epoch_120 $OUT/checkpoints/rq4-sufu-code-first
cp -r t5_llm/models/codet5-base_mbjp_codeproof/2025-09-23_23-07-57/epoch_40 $OUT/checkpoints/rq4-java-type-first
cp -r t5_llm/models/codet5-base_mbjp_proofcode/2025-09-24_20-35-59/epoch_15 $OUT/checkpoints/rq4-java-code-first

# Score records live in the git-tracked evidence store
# (artifacts/major_revision_strong_baselines_20260824/scores/); they are not
# duplicated into this bundle.

echo DONE; du -sh $OUT; du -sh $OUT/*;
