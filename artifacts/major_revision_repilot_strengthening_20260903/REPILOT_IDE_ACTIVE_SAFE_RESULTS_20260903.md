# Repilot IDE-only strengthening results (2026-09-03)

## Experimental evidence

The formal run uses the exact MBJP test prefix, the paper-comparison T5Gemma
checkpoint, 10 candidates per problem, and the existing full-output scorer.
SynCode and the structural delimiter helper are not imported by the runner.

| Variant | Scope | Pass@1 | Pass@10 | Compile errors | JDT queries | Proposal-cache hits |
|---|---:|---:|---:|---:|---:|---:|
| Frozen sound-default Repilot/JDT | 67 x 10 | 10/67 | 23/67 | 112/670 | 18,653 | 0 |
| Repilot JDT + safe ACTIVE + full IDE capabilities/5 s timeout | 67 x 10 | 10/67 | 23/67 | 112/670 | 17,963 | 9,736 |
| Repilot JDT + strict upstream ACTIVE | 10 x 10 pilot | 1/10 | 4/10 | 68/100 | — | — |
| Repilot JDT + safe ACTIVE (same 10-task pilot) | 10 x 10 pilot | 2/10 | 5/10 | 18/100 | — | — |

The safe formal run produced 670/670 candidates and no missing outputs. Its
trajectory totals are 1,227 ACTIVE starts, 936 direct ACTIVE accepts, 497 safe
fallbacks, and zero ACTIVE rejections. Wall-clock generation time was
1,927.9 s (including 8.0 s model initialization and 1.8 s JDT startup).

The training-only replay of 608 known-correct MBJP programs checked 58,045
suffix tokens and found zero false prunes under the same safe policy. The
replay record is
`repilot_ide_active_safe_async_training_audit_20260903.json`.

## Interpretation

The IDE settings and proposal memoization reduce redundant JDT calls and keep
the original soundness contract, but they do not change the model's sampling
distribution. Consequently the full Pass@1/Pass@10 values are unchanged from
the frozen sound-default row. The strict paper ACTIVE heuristic is not adopted
as the headline row: even on the 10-task pilot it has more compilation errors
and lower Pass@1/Pass@10 than the safe policy, while the complete training
replay has already shown that proposal-list exhaustiveness is not sound for
this benchmark.

## Missing work and manuscript action

No additional Repilot accuracy rerun is justified by these results. RQ3 should
retain the frozen upstream-faithful Repilot row and add the new row only as
`Repilot (IDE completion + safe ACTIVE)` with a footnote that it is a
soundness-preserving implementation strengthening, not a new grammar method.
The table should report the full-run Pass@1 as the primary metric; the
Pass@10 value and JDT/caching counts belong in an implementation-cost or
appendix note. Do not combine this row with SynCode or relabel it as a
syntax-mask baseline.
