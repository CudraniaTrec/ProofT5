# HumanEval recipe-search validation protocol (2026-09-09)

Framework for iterating TyFlow training recipes without consuming the frozen
16-task HumanEval-Java v15 test. Applies to any recipe AFTER v3 (v3 itself
runs under its own pre-registered protocol).

## Validation holdout (frozen)

- 32 HumanEval-Java v15 TRAIN tasks, selected by seeded shuffle (seed 273567)
  over the 146-task train split; indices and hash recorded below. These tasks
  never enter the training data of any candidate recipe.
- Task dir: `Utils/data/java_hev15_valholdout32_t5gemma2_20260909/`
  (test.pkl sha256 6915c7a37b123f34492913f12ec5688d7c4b0ccc902a06eaac8edf63faaa984c)
- Training variant for candidates: `Utils/data/java_union_minus_val32_t5gemma2_20260909/`
  (1136 rows = 1168-32; train.pkl sha256 b7b3258224fb0504a58578556bf966c4be78fa44208ba6caa00513f388071553)
- Contamination note: models trained on the FULL union (v2, v3) have seen
  these 32 tasks; their holdout scores are replay diagnostics only and are
  never used for recipe selection.

## Selection rule

1. Any number of candidate recipes may be trained on union-minus-val32
   (any staging, order, epochs, lr); each is evaluated ONCE on the 32-task
   holdout with the frozen decode protocol (beam 10, lp 0.1, multiplier 20,
   Coq timeout 20s, fail-closed; identical scorer).
2. The winning recipe = highest holdout pass@10, tie-broken by pass@1, then
   FSP. The comparison table (all candidates, all scores) is retained.
3. The winner is retrained on the FULL 1168-row union with the identical
   recipe, and that final model is evaluated exactly once on the frozen
   16-task test. Baseline comparator stays the frozen v2 baseline.

## Commitments

- The 16-task test never participates in recipe choice.
- Every candidate's holdout score and recipe is recorded, winners and losers
  alike.
- If the final winner's test run does not beat the baseline, that is the
  reported outcome; no further test runs under this framework.
