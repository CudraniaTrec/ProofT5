# HumanEval staged-retrain protocol v3 (2026-09-09)

Supersedes v2 after its negative outcome (TyFlow v2: pass@1 2/16, pass@10 4/16
vs frozen baseline 2: pass@1 1/16, pass@10 5/16; frozen under
artifacts/humaneval_aligned_retrain_20260909/).

## Diagnosis motivating v3 (evidence in the v2 artifact package and git)

The published joint23 lineage continued from a dedicated MBJP-673 formal
30-pass stage (`mbjpcoq_t5gemma2_2b_corrected_formal30pass_lr1em5_8gpu_b5_20260715_163958`)
before its HumanEval/GFG stages. The shared OpenCoder pretrain carries a
32,216-rule vocabulary while the Java task family uses 282,305 rules, so
88.6% of the decision vocabulary is newly initialized at the first Java
formal stage; the published lineage absorbed this in a dedicated stage plus
successive continuations. v2 trained a single mixed 30-pass run from the
OpenCoder pretrain, and its failure mode (5 tasks failing to produce any
complete valid derivation within the 747-step budget) is consistent with an
under-absorbed decision representation.

## v3 recipe (mirrors the published staging; baseline comparator frozen)

Baseline: UNCHANGED — the frozen v2 baseline checkpoint and its score JSON
(pass@1 1/16, pass@10 5/16) remain the comparator. No further baseline runs.

TyFlow-2B, two stages, final-checkpoint selection per stage, no test-side
information at any point:

| stage | data | init | budget | output |
|---|---|---|---|---|
| 1 | MBJP-608 proof rows (clean-673 `benchmark==mbjp` rows; same rows as inside the v2 union; zero v15-test overlap, verified by the v2 build) | shared OpenCoder pretrain `pretrain_t5gemma2_2b_retok_corrected_formal5pass_lr1em5_8gpu_b5_20260715_1412` (sha256 2ff91da8...) | lr 1e-5, batch 5 x 8, 30 passes, seed 273567 | `Utils/models/Modelmbjp608_stage1_from_sharedpretrain_formal30_20260909/` |
| 2 | the frozen v2 union (1168 rows, train.pkl sha256 26e5279c...) | stage-1 last checkpoint | lr 1e-5, batch 5 x 8, 30 passes, seed 273567 | `Utils/models/Modelv3_staged_union_from_stage1_formal30_20260909/` |

## Evaluation (one shot, unchanged)

Identical to v1/v2: HumanEval-Java v15 test (16 tasks), proof-constrained
decoder, beam 10, length penalty 0.1, candidate multiplier 20, Coq timeout
20 s, fail-closed; scored by score_java_no_write.py. Practical budget rule
(following the frozen-package GFG-task-44 precedent): a task whose search has
not terminated after ~2.5-3 h of wall time is abandoned and counted as ten
failures (fail-closed), with the abandonment recorded in the score notes.

## Acceptance (user-specified)

TyFlow v3 must clearly beat the frozen v2 baseline on the 16-task test:
pass@1 > 1/16 and pass@10 > 5/16, with the pass@10 > pass@1 gap preserved.

## Commitments

- This protocol is frozen before stage 1 launches.
- The 16-task test is opened exactly once for v3.
- If v3 fails the acceptance criteria, the result is reported as measured and
  the paper is not updated; any further recipe change goes through a new
  pre-registered protocol whose model selection must be train-side or
  validation-side only (never the 16-task test).
- The recipe-iteration history (v1 dual1082 -> v2 union -> v3 staged) is
  disclosed in the artifacts and available to the revision letter.

## Outcome (2026-09-09, recorded after the run)

v3 failed acceptance: pass@1 1/16, pass@10 1/16 (vs frozen baseline 1/16, 5/16).
Mechanism: beam diversity collapse (pass@10 == pass@1); staged lr-1e-5/30-pass
training yields over-confident near-clone candidates. The follow-up recipe-search
framework (holdout-32) selected v4 (staged + lr 2e-6 x 5 passes; holdout 3/32 ->
4/32, beating v2' 1/32 -> 4/32 on the pass@1 tie-break). The v4 full-union retrain
consumed the framework's single test run and failed: pass@1 0/16, pass@10 2/16,
CER 0.0% on 130/160 candidates (3 tasks budget-exhausted fail-closed: 5, 11, 12).
Per the framework commitment, no further test runs; scores frozen in
artifacts/humaneval_aligned_retrain_20260909/.
