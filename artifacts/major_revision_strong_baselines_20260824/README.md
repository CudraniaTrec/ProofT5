# Java strong-baseline result supplement (2026-08-24)

This is a new, non-frozen supplement. It does not replace or modify
`artifacts/major_revision_20260824`, its checkpoints, candidates, scores, or
manifest. The experiments reuse the ordinary frozen T5Gemma2 weights and
change the inference procedure only.

## Complete formal scores

Each cell is `pass@1 / pass@10 [compile errors among 10N candidates]`.

| benchmark | ordinary | SynCode | Repilot/JDT | iterative | ProofT5 |
|---|---:|---:|---:|---:|---:|
| MBJP (67) | 9 / 22 [198] | not run | 10 / 16 [164] | not run | 17 / 29 [3] |
| HumanEval-Java v15 (16) | 2 / 4 [47] | 0 / 1 [116] | 2 / 2 [42] | 2 / 2 [27] | 8 / 9 [2] |
| TransCoder-GFG v13 (103) | 14 / 28 [258] | not run | 12 / 23 [158] | not run | 31 / 48 [28] |

HumanEval is ancestor-mixed exploratory. On its lineage-unseen 11-task subset,
SynCode is 0/11 and 1/11; Repilot and iterative are both 1/11 and 1/11;
ordinary is 1/11 and 3/11; ProofT5 is 4/11 and 5/11.

The iterative round-0 export is an exact paired control for the final repaired
candidates. It scores 2/16 and 2/16 with 46 compile-error candidates; repair
scores 2/16 and 2/16 with 27 compile-error candidates. Per-round trajectories
record 111 initially compiling and 133 finally compiling candidates. The
surface-validity improvement does not change the functional solved set.

## Controlled iterative extension completed 2026-08-25

The same compiler-feedback protocol and exact round-0 export are now complete
on all requested Java benchmarks. MBJP uses the archived paper-recovery
checkpoint and is therefore reported separately from the older clean
checkpoint table above.

| benchmark | round-0 pass@1 / pass@10 [compile errors] | final pass@1 / pass@10 [compile errors] | model / repair calls |
|---|---:|---:|---:|
| HumanEval-v15 (16) | 2 / 2 [46/160] | 2 / 2 [27/160] | 241 / 81 |
| MBJP paper recovery (67) | 8 / 17 [133/670] | 8 / 17 [83/670] | 945 / 275 |
| GFG-v13 (103) | 12 / 23 [190/1030] | 12 / 24 [118/1030] | 1,387 / 357 |

The complete GFG artifact repairs 83 initially non-compiling candidates and
adds one pass@10 solved task. The first attempted GFG merge is deliberately
not promoted: a safely interrupted shard had complete candidate files but no
terminal manifest, so the merger failed closed and the follow-on diagnostic
score recorded all 1,030 candidates missing. The valid result files include
`complete` in their names and have zero missing candidates.

## Interpretation boundary

Repilot is a faithful Java/model adapter around the upstream modified-JDT token
pruning mechanism, not an unchanged Defects4J reproduction. Iterative
refinement is a controlled matched-weight diagnostic, not a strong
instruction-following baseline, because these frozen seq2seq weights were not
trained on repair prompts. The frozen ordinary results used beam search while
these adapters use greedy rank 0 plus fixed-seed sampling for ranks 1--9; a
plain-Hugging-Face matched-sampling control is required to isolate the causal
effect of the constraints.

The formal HumanEval SynCode run has all 160 candidates. It records 20 upstream
fallbacks to unconstrained decoding and 78 fail-closed generation timeouts; the
functional scorer records 116 compile errors and two execution timeouts. This
pathological integration behavior is part of the result and prevents an
unqualified claim that every candidate was CFG-constrained. Its accumulated
per-candidate time is 21,770.7 s; 20,824 output tokens are observed for the 82
non-timeout candidates, while the full token total is intentionally null.

Protocol and integration details are in
`docs/experiments/JAVA_FROZEN_T5GEMMA_STRONG_BASELINES_20260824.md`.
