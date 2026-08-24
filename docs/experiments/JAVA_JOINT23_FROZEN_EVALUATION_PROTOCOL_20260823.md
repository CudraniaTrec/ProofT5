# Java joint23 frozen evaluation protocol (2026-08-23)

This protocol is frozen before opening any new held-out output from the final
dual HumanEval/GFG rehearsal checkpoint. It separates strict held-out results
from the user-authorized seen-replay diagnostic.

## Frozen checkpoint and selection

- checkpoint:
  `Utils/models/Modeljoint23_dual_hegfg_from_heonly_lr2e6_p5_20260823/last_model.ckpt`
- SHA-256:
  `6740c1f15dfbc6fabcc55ceafa2f6d5624d9e3197336c1bcdc58acb6ae3e2791`
- training task:
  `java_humaneval_v15_transcoder_v13_dual1082_t5gemma2_20260823`
- validation: empty;
- selection evidence: prespecified training-only functional probes;
- completed gate: HumanEval 7/7 top-1 among terminating beam-1 rows and GFG
  2/2 pass@1/pass@10 under the default decoder;
- unresolved gate item: HumanEval training probe index 7 does not terminate
  under the fixed generation budget.

The checkpoint is frozen as the best *diagnostic* joint candidate before any
evaluation below. No result below may be used to choose another checkpoint or
to continue training and then reopen the same strict test as if it were fresh.

## Prespecified evaluations

All Coq runs use the formal prefix-constrained decoder, beam 10, length penalty
0.1, candidate multiplier 20, task-config generation maximum, Coq timeout 20
seconds, and functional Java scoring timeout 10 seconds. Final-only checking
and beam-1 are not substitutes for these reported pass@1/pass@10 runs.

Execution note added without changing the protocol: the initial single-GPU
strict-16 run completed ID 0, then was stopped after spending over 20 minutes
on ID 1. Its completed ID-0 files are preserved under tag
`joint23_dual_hegfg_hev15_strict16_frozen_20260823`. The remaining immutable
ID set is evaluated as two disjoint shards on the same physical GPU:
IDs 1--7 under `joint23_dual_hegfg_hev15_strict16_shardA_20260823` and IDs
8--15 under `joint23_dual_hegfg_hev15_strict16_shardB_20260823`. Final scoring
requires an auditable 0--15 merge with ten candidates and beam metadata per
ID; partial-shard nominal denominators are invalid.

1. HumanEval v15 strict held-out set:
   `java_humaneval_mbjp_native_semanticsupport_split90_10_t5gemma2_20260822_v15`,
   test 16. This set has no overlap with the checkpoint's v15 training rows.
2. TransCoder-GFG v13 strict held-out set:
   `java_transcoder_gfg_mbjp_native_prompt_split80_20_t5gemma2_20260819_v13`,
   test 103. The checkpoint trained on the corresponding v13 training side.
3. HumanEval 66-row seen-replay diagnostic:
   `java_humaneval_v13_seen33_heldout33_diagnostic_t5gemma2_20260822`, test 66.
   Under v15 membership, 54/66 rows occur in training. Report the 54 trained
   and 12 untrained rows separately. Never call the aggregate held out.

The strict results answer generalization; the 66-row result answers only
whether continued training can reproduce included functions and whether that
fit transfers at all to its 12 untrained rows.

## Decision rule

- Compare HumanEval-v15 Coq once against the already frozen ordinary v15
  result, 2/16 pass@1 and 4/16 pass@10.
- Compare GFG-v13 Coq once against the matching frozen ordinary v13 result
  recorded in the v13 experiment ledger.
- Preserve negative results. Coq is called an improvement only if its integer
  solved count exceeds the matching ordinary count under the same split and
  candidate budget.
- The 66-row diagnostic cannot replace either strict result, even if its
  aggregate score is high or resembles MBJP.

## Post-freeze lineage-overlap correction (2026-08-23)

The original freeze correctly established zero overlap with the *direct* v15
training rows, but it did not account for all ancestor checkpoints. The final
joint Coq checkpoint descends through the GFG-v14 Coq model from the clean-673
Coq parent. Five of the 16 HumanEval-v15 test task IDs occur in that ancestor's
HumanEval training membership: test indices `3,6,7,10,12`.

The full 16-row result must therefore be called **split-held-out but
ancestor-mixed**, not fully held out. A matched re-score on the 11 task IDs
unseen throughout this recorded checkpoint lineage gives:

| model | pass@1 | pass@10 |
|---|---:|---:|
| ordinary T5Gemma2 | 1/11 (9.09%) | 3/11 (27.27%) |
| frozen joint Coq | 4/11 (36.36%) | 5/11 (45.45%) |

This correction does not change checkpoint selection or generation. It only
narrows the reportable denominator using membership fixed independently of
functional outcomes. The authoritative row IDs, lineage evidence, score paths,
and hashes are recorded in
`docs/audits/JAVA_HUMANEVAL_V15_ANCESTOR_OVERLAP_AUDIT_20260823.json`.
