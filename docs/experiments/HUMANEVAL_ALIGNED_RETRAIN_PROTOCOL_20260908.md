# HumanEval aligned-retrain protocol (2026-09-08)

This protocol is written and frozen **before** any new training run or any new
held-out output is opened. It defines a single aligned retraining of both
2B models for the RQ1 HumanEval row, with identical data, budget, selection
rule, and decoding budget on both sides.

## Motivation and scope

The current HumanEval row compares two differently-initialized lineages: the
ordinary T5Gemma2-2B (trained from the HF base on a plain-format curriculum)
and the joint ProofT5/TyFlow checkpoint (trained through the clean-673 ->
GFG-v14 -> heonly -> dual-1082 lineage, whose ancestry saw 5 of the 16 test
task IDs; see `JAVA_HUMANEVAL_V15_ANCESTOR_OVERLAP_AUDIT_20260823.json`).
This experiment replaces both rows with one aligned pair whose lineage is
leak-free for all 16 test tasks.

User-approved design decisions (2026-09-08):

1. Data scope: the frozen dual-1082 curriculum (541 HumanEval-Java v15 +
   541 TransCoder-GFG v13 training occurrences) for **both** models.
2. Initialization: both models start from a shared, benchmark-clean starting
   point (see below); the old ProofT5 lineage is not reused.
3. Decoding: unchanged from the published rows: beam 10 on both sides.
   No sampling decoder is introduced in this protocol.

## Frozen inputs (SHA-256)

| asset | path | sha256 |
|---|---|---|
| proof-format train | `Utils/data/java_humaneval_v15_transcoder_v13_dual1082_t5gemma2_20260823/train.pkl` | `99c24b9c0646155cb9e6fa4cca647b91878de97a474f87706596433d966f7712` |
| plain-format train | `Utils/data/java_humaneval_v15_transcoder_v13_dual1082_t5gemma2_20260823/train_t5_plain_format.json` | `20614ceea4ca43a64e774622d0824293c102393b8847a6ba9872b92289ef7449` |
| held-out test (16) | `Utils/data/java_humaneval_mbjp_native_semanticsupport_split90_10_t5gemma2_20260822_v15/test.pkl` | `38be37d0c76bf708cf67413fab7d993a140241998442db23687e4d3d6ba58b79` |
| shared pretrain ckpt | `Utils/models/Modelpretrain_t5gemma2_2b_retok_corrected_formal5pass_lr1em5_8gpu_b5_20260715_1412/last_model.ckpt` | `2ff91da81d96a3f7dd7814111f196ed836f4c9c2c1d568348515bdfa53184811` |

The test pickle hash equals the `dataset_pickle_sha256` recorded in the
frozen 2026-08-24 score JSONs: the held-out set is bit-identical to the
published one.

Leakage status: the shared pretrain checkpoint is the OpenCoder
representation-adaptation stage (`retok_corrected`, 5 passes); the frozen
2026-08-24 lineage audit traces all HumanEval-v15 test exposure to stages
**after** this pretrain (clean-673 and later). Neither new model is trained
on any checkpoint past the shared pretrain, so all 16 test tasks are unseen
by both new models. The ancestor-mixed caveat and the 11-task subset
reporting attached to the old rows are retired by this experiment.

## Training recipe (identical budget, established per-side recipes)

Both sides train for the same 30-pass budget and keep only the **final
checkpoint**. No validation set exists in either path; no checkpoint may be
selected by any test-side or functional outcome.

| side | entrypoint | data | init | hyperparameters (mirroring the published recipes) | output |
|---|---|---|---|---|---|
| TyFlow-2B (proof) | `run.py` via `accelerate launch --num_processes=8` | dual1082 task (proof loader) | shared pretrain (`--pretrain_name pretrain_t5gemma2_2b_retok_corrected_formal5pass_lr1em5_8gpu_b5_20260715_1412`, `pretrain_model_type=last`) | task config as frozen: lr 1e-5, batch 5/GPU x 8, max_epoch 29 (30 passes), seed 273567 | `Utils/models/Modeljoint_dual1082_from_sharedpretrain_formal30_20260908/` |
| T5Gemma2-2B (plain) | `t5_llm/finetune_t5gemma2.py` | dual1082 `train_t5_plain_format.json` | HF base `Utils/models/t5gemma-2-1b-1b` | lr 5e-5, batch 5, 30 epochs, warmup 5, seed 273567 (the established `b5_lr5em5_pass30` recipe) | `t5_llm/models/t5gemma2-2b_java_dual1082_hegfg_plain_b5_lr5em5_pass30_20260908/` |

Known, openly-declared asymmetries (same as the published 2B rows): the proof
side starts from the shared representation-adaptation pretrain because the
method's output space is the formal derivation vocabulary; the plain side
starts from the HF base because it emits Java directly. Both are described in
the paper's implementation details.

## Evaluation (one shot)

After both trainings finish:

1. Generation, HumanEval-Java v15 test (16 tasks), 10 ordered candidates per
   task, beam 10, fail-closed:
   - TyFlow-2B: `run.py --task <v15> --eval --model_output_task
     joint_dual1082_from_sharedpretrain_formal30_20260908` with the frozen
     decode settings (proof-constrained beam, length penalty 0.1, candidate
     multiplier 20, task-config generation maximum); shard across GPUs as in
     the 2026-08-23 protocol if needed.
   - T5Gemma2-2B plain: `finetune_t5gemma2.py --generate_only` on
     `test_t5_plain_format.json` of the v15 task (HF beam, max 1024,
     penalty 1.0).
2. Scoring: `score_java_no_write.py` with the task's frozen test pickle,
   10-second functional timeout, Java 17; one score JSON per side written
   under a new `artifacts/` package with hashes of datasets, checkpoints,
   candidate outputs, and scores.
3. Reporting: pass@1/pass@10/FSP/CER for both sides, plus exact paired
   McNemar tests on the 16 tasks and Wilson intervals. All four numbers are
   reported as measured.

## Commitments

- This protocol is frozen before launch. Training hyperparameters, data,
  selection rule, and decode configuration may not be changed after any
  test-side output has been seen.
- The evaluation is run once per side. The outcome is reported regardless of
  direction. If the result does not show the expected pattern, the follow-up
  is diagnosis of the method or setup under a **new** pre-registered
  protocol; re-running the same evaluation to obtain a different draw is not
  an accepted action.
- No checkpoint, split, or decode setting may be chosen using the 16 test
  tasks or their scores.
- Paper integration, if the result is adopted, must update: the RQ1
  HumanEval row, the appendix benchmark/statistics text, any affected
  failure-taxonomy counts, and the revision change log, with the protocol
  change disclosed in the response letter.
