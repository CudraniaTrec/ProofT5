# Baseline strengthening protocol (2026-09-09)

Goal (user-directed): raise the T5Gemma2-2B baseline on HumanEval-Java so the
gap to the published TyFlow row narrows. All baseline recipe/decode choices are
made on the 32-task validation holdout; the 16-task test is opened exactly once
for the winning configuration.

## Scope and honesty constraints

- The TyFlow published row (50.00 / 56.25) is untouched.
- Whatever the strengthened baseline produces on the 16-task test becomes the
  reported baseline row, favorable or not. If any metric of the strengthened
  baseline exceeds the TyFlow row, that too is reported.
- The paper edit (replace the baseline row vs. add a stronger-baseline row) is
  decided AFTER the number exists, and both rows' provenance is documented.

## Phase 1 — decode-variant selection on holdout-32

Model: plain baseline trained on `union_minus32_plain_train.json` (1136 rows;
same curriculum family as the v2 baseline minus the 32 holdout tasks), lr 5e-5,
batch 5, 30 epochs, seed 273567, output
`t5_llm/models/t5gemma2-2b_java_unionminus32_plain_b5_lr5em5_pass30_20260909/`.

Variants (same trained model, three decodes via `t5_llm/gen_baseline_variants.py`):
1. beam10: HF beam 10, penalty 1.0 (published protocol)
2. sample10: 10 i.i.d. samples, T=0.8, top_p 0.95
3. few3_beam10: 3-shot prompt (three fixed train-split exemplars, indices 0-2
   of the non-holdout train rows; fixed before any evaluation) + beam 10

Scored with score_java_no_write.py on
`java_hev15_valholdout32_t5gemma2_20260909`. Selection: highest pass@10;
tie-break pass@1, then FSP.

## Phase 2 — single test run

The winning variant is applied to the existing full-union baseline checkpoint
(`t5gemma2-2b_java_union_plain_b5_lr5em5_pass30_20260909`; for few-shot, the
same exemplars) and evaluated once on the 16-task test. That number is the
strengthened baseline row. No further test runs in this protocol.
