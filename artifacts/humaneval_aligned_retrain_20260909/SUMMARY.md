# Consolidated test-data summary: baseline strengthening & recipe search (2026-09-08 .. 2026-09-10)

All numbers below are measured with the frozen protocols in docs/experiments/,
scored by score_java_no_write.py (Java 17, 10 s functional timeout, fail-closed),
and frozen with SHA-256 sums in SHA256SUMS. Decoding for all TyFlow runs:
proof-constrained beam 10, length penalty 0.1, candidate multiplier 20.
All baseline runs: HF beam 10, no few-shot prompting.

## 1. Final paper state (RQ1 Table 1, 2B Java rows)

| benchmark | model | pass@1 | pass@10 | FSP | CER |
|---|---|---:|---:|---:|---:|
| MBJP (67) | T5Gemma2-2B | 13.43 | 32.84 | 7.46 | 29.55 |
| MBJP (67) | TyFlow-2B | 25.37 | 43.28 | 6.36 | 0.45 |
| HumanEval (16) | T5Gemma2-2B (strengthened) | 31.25 | 37.50 | 6.50 | 24.38 |
| HumanEval (16) | TyFlow-2B | 50.00 | 56.25 | 4.75 | 1.30 |
| GFG (103) | T5Gemma2-2B (strengthened) | 19.42 | 33.01 | 7.10 | 13.69 |
| GFG (103) | TyFlow-2B | 30.10 | 46.60 | 5.81 | 2.75 |

TyFlow rows are the published frozen checkpoints, unchanged throughout.
Paired exact McNemar on HumanEval (n=16): pass@1 p=0.375, pass@10 p=0.250 —
directional only; the paper avoids significance claims on this test.

## 2. Strengthened baselines (adopted into the paper)

| benchmark | recipe | holdout selection | test result | replaced row |
|---|---|---|---|---|
| HumanEval | union-1168, lr 1e-5, 30 passes | 20 checkpoints (4 recipes x 5 epochs) on holdout-32; winner e20 (28.12/37.50) | 31.25 / 37.50 / 6.50 / 24.38 | 12.50 / 25.00 / 7.88 / 29.38 |
| GFG | MBJP-608+GFG-414, lr 1e-5, 30 passes | 5 epochs on holdout-60; winner e15 (11.67/28.33) | 19.42 / 33.01 / 7.10 / 13.69 | 13.59 / 27.18 / 7.74 / 25.05 |

Key finding: lr 5e-5 with last-checkpoint selection (the old recipe) overfits
and underestimates the base model; lr 1e-5 with holdout-selected epochs recovers
+18.75 pp (HumanEval) and +5.83/+5.83 pp (GFG) of baseline pass@1/pass@10.
Score files: scores/sweep_b?_e?_score.json (20), scores/gsweep_e?_score.json (5),
scores/he_bBfinal_e20_baseline_test16_score.json,
scores/gfg_gBfinal_e15_baseline_test103_score.json.

## 3. TyFlow alignment-retrain experiments (not adopted; negative results)

Fresh-lineage TyFlow-2B re-trains from the shared OpenCoder pretrain
(32,216-rule vocabulary; the Java task family uses 282,305 rules), evaluated
once each on the frozen HumanEval-16 test:

| recipe | pass@1 | pass@10 | CER | note |
|---|---:|---:|---:|---|
| v1: dual-1082 single stage | 0/16 | 1/16 | 9.38% | curriculum too thin |
| v2: union-1168 single stage | 2/16 | 4/16 | 15.45% (110 tested) | best pass@1 of the four |
| v3: MBJP608 stage + union, lr 1e-5 x 30 | 1/16 | 1/16 | 14.29% (140) | beam diversity collapse (pass@10 == pass@1) |
| v4: MBJP608 stage + union, lr 2e-6 x 5 (holdout-selected) | 0/16 | 2/16 | 0.00% (130) | CER mechanism clean; semantics unchanged |

Conclusion: within this compute budget, fresh lineages reach at most 2/16
pass@1 — far below the published joint23 row (8/16), which reflects the
multi-month staged lineage. The published rows stand.

## 4. TyFlow recipe tournament (holdout-32; 16-task test never opened)

| recipe | holdout pass@1 | holdout pass@10 |
|---|---:|---:|
| v4' staged + lr 2e-6 x 5 | 9.38% | 12.50% |
| v2' single-stage | 3.12% | 12.50% |
| v3' staged + lr 1e-5 x 30 | 3.12% | 15.62% |

v3' won on pass@10, but its full-union version (v3) had already consumed the
single test opening and failed; per protocol no further test runs were made.

## 5. Discipline record

- Every test opening was preceded by a frozen protocol in docs/experiments/
  (six protocol documents).
- Recipe/checkpoint selection used only validation holdouts (32-task
  HumanEval, 60-task GFG, both seeded and hash-frozen); no test-side
  information influenced any selection.
- The HumanEval-16 test was opened: v1, v2, v3, v4 (TyFlow diagnostics,
  reported regardless of outcome), and once for the strengthened baseline.
  The GFG-103 test was opened once for the strengthened baseline.
- A concurrent session on this machine deleted docs/ (restored) and wrote one
  score file into this package (holdout_v3r_score.json, kept, verified
  consistent with our own v3' holdout run).
