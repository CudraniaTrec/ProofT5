# HumanEval aligned-retrain protocol v2 (2026-09-09)

Supersedes protocol v1 (2026-09-08) for the RQ1 HumanEval row. v1 was run to
completion, frozen under `artifacts/humaneval_aligned_retrain_20260909/`, and
did not meet either acceptance criterion (TyFlow 0/16 vs baseline 2/16 at
pass@1; no pass@1->pass@10 gap). Diagnosis: v1's curriculum (dual-1082 only,
no MBJP stage) was too thin for the proof-representation model, which in the
published lineage learned the Java decision-sequence task on 673 MBJP tasks
first.

v2 therefore mirrors the published Java recipe for **both** models: the same
union of the three published Java training splits, same 30-pass budget,
last-checkpoint selection, and the unchanged one-shot evaluation.

## Frozen inputs (SHA-256)

| asset | path | sha256 |
|---|---|---|
| proof train (1168) | `Utils/data/java_mbjp_hev15_gfg414_union_t5gemma2_20260909/train.pkl` | `26e5279ca05e08583958a46719ca93b85bf89a83c0d2fa5ee2c9e1302c638111` |
| plain train (1168) | `Utils/data/java_mbjp_hev15_gfg414_union_t5gemma2_20260909/train_t5_plain_format.json` | `ee3dd36cda660e7a02233eded0a3260045a07433d86deb0dde9aea3ea853c5ca` |
| rules (task family) | `Utils/data/java_mbjp_hev15_gfg414_union_t5gemma2_20260909/rules.pkl` | `112c62c57ba1e6a27b3fc550f006e236a452e22c621e9807f6ded13d73e1655f` |
| held-out test (16) | `Utils/data/java_humaneval_mbjp_native_semanticsupport_split90_10_t5gemma2_20260822_v15/test.pkl` | `38be37d0c76bf708cf67413fab7d993a140241998442db23687e4d3d6ba58b79` |
| shared pretrain ckpt | `Utils/models/Modelpretrain_t5gemma2_2b_retok_corrected_formal5pass_lr1em5_8gpu_b5_20260715_1412/last_model.ckpt` | `2ff91da81d96a3f7dd7814111f196ed836f4c9c2c1d568348515bdfa53184811` |

Curriculum composition (identical task set, proof and plain formats):
608 MBJP (clean-673 rows with `benchmark==mbjp`; the 65 HumanEval rows of that
dir are excluded) + 146 HumanEval-Java v15 train (fixed split) + 414
TransCoder-GFG v13 train. Leakage check (run exhaustively at build time): 0 of
the 1168 rows shares a java body with any of the 16 v15 test tasks; the plain
mirror has 0 rows sharing a test-case body with the v15 test.

## Training recipe (identical budget to v1)

| side | data | init | hyperparameters | output |
|---|---|---|---|---|
| TyFlow-2B (proof) | union `train.pkl` | shared pretrain, `model_type=last` | lr 1e-5, batch 5/GPU x 8, 30 passes, seed 273567 | `Utils/models/Modeljoint_v2_union_mbjp608_he146_gfg414_from_sharedpretrain_formal30_20260909/` |
| T5Gemma2-2B (plain) | union `train_t5_plain_format.json` | HF base `t5gemma-2-1b-1b` | lr 5e-5, batch 5, 30 epochs, warmup 5, seed 273567 | `t5_llm/models/t5gemma2-2b_java_union_plain_b5_lr5em5_pass30_20260909/` |

Selection: final (last) checkpoint on both sides; no test-side or functional
outcome may influence checkpoint choice.

## Evaluation (one shot, unchanged from v1)

Same as v1: HumanEval-Java v15 test (16 tasks), 10 ordered candidates per
task, beam 10, fail-closed; TyFlow-2B via the proof-constrained decoder
(checkcoq=True, length penalty 0.1, candidate multiplier 20, Coq timeout 20s,
task-config generation maximum), sharded; T5Gemma2-2B via HF beam (max 1024,
penalty 1.0). Both scored by `score_java_no_write.py` (Java 17, 10 s
functional timeout). Report pass@1/pass@10/FSP/CER as measured, plus exact
paired tests on the 16 tasks.

## Acceptance criteria (user-specified, unchanged)

1. TyFlow-2B improves over T5Gemma2-2B on the same test set.
2. TyFlow-2B shows a pass@1 -> pass@10 improvement (pass@10 > pass@1).

## Commitments

Identical to v1: protocol frozen before launch; one evaluation per side;
outcome reported regardless of direction; no re-roll of the same protocol; a
negative outcome leads to diagnosis under a further pre-registered protocol;
paper integration only if the result is adopted, with the protocol change
disclosed in the revision letter.
