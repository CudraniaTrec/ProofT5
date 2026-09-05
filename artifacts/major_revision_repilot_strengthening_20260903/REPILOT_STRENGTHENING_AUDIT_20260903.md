# Repilot strengthening audit (2026-09-03)

## What the paper actually specifies

The Repilot paper describes a completion engine built on Eclipse JDT and
incremental syntax/semantic analysis. The engine is used as a feasibility
oracle: a token is pruned when the strict completion set is empty, and an
unknown result is accepted. The paper does not specify a separate SynCode-like
grammar mask on every token. The implementation consequently bypasses
punctuation and Java keywords and queries JDT for identifier-like tokens. The
paper's strict-completion soundness argument assumes that the completion set
is exhaustive; the modified IDE endpoint is not itself a proof-producing Java
parser.

Sources:

- https://arxiv.org/html/2309.00608
- https://github.com/ise-uiuc/Repilot

## Findings in the frozen adapter

The upstream-faithful row is not silently changed:

- JDT newCompletion is queried only under the upstream trivial-feasibility
  bypass.
- A null completion result is accepted as unknown.
- Empty completion results are rejected.
- The top-p support is restored when all tried proposals are rejected.
- ACTIVE completion propagation is disabled in the paper-facing row because
  the original aggressive policy is not sound on this benchmark.

The training replay explains the apparent weakness of the old row. Querying
JDT on every token falsely rejects 56/608 known-correct programs; the
aggressive ACTIVE policy falsely rejects 293/608. These are not valid stronger
baselines.

## Strengthened, separately labelled option

`repilot_jdt_ide_active_safe` enables ACTIVE completion only as an affirmative
hint. Tokens outside a JDT-proposed prefix are rechecked by the ordinary
JDT/trivial-feasibility path rather than rejected solely because they are
absent from the proposal list. Its replay has zero false-pruned programs, with
1,448 completion starts and 538 safe fallbacks.

The final asynchronous-IDE replay of the same 608 training programs checked
58,045 suffix tokens with 18,420 JDT queries and again produced zero
false-pruned programs (1,166 ACTIVE token accepts, 1,448 starts, and 538 safe
fallbacks). Its record is
`repilot_ide_active_safe_async_training_audit_20260903.json`.

The `--ide_best_effort` mode advertises the full completion capability set and
raises the modified completion-handler timeout to 5 seconds by default. The
optional `--ide_join_completion` flag sets JDT's lifecycle-join property before
every completion; it is retained as a strict diagnostic but is too slow for
the formal 67-task rerun. These are IDE settings, not a second syntax checker,
and therefore remain a Repilot-only strengthening. The prior
`repilot_jdt_active_safe` replay without the IDE settings is retained as a
diagnostic; it is not substituted into the frozen upstream row.

This mode preserves the exact benchmark prefix, model, candidate budget, and
hidden-test isolation. Existing frozen score trees and the upstream-faithful
Repilot result are untouched.

The resulting full MBJP run (67 problems x 10 candidates) produced 670/670
candidate files and scored 10/67 Pass@1 and 23/67 Pass@10. The full score and
trajectory summaries are recorded in
`REPILOT_IDE_ACTIVE_SAFE_RESULTS_20260903.md`; the output directory is
`Utils/output/mbjp_original_test_t5gemma2_20260731_test_ans/repilot_ide_active_safe_b10_20260903`.

## RQ3 rerun protocol

Run a 3--5 task, one-candidate smoke test and inspect the trajectory fields
(completion_queries, active_completion_fallbacks, and rejected-token
examples). Only after the smoke test and a fresh complete-candidate audit pass
should a 67-task x 10-candidate rerun be launched. The final table must
contain separate rows for the upstream-faithful Repilot/JDT adapter and the
IDE-best-effort safe-ACTIVE variant; the latter must not replace or overwrite
the frozen row. Synchronised generation and checker-cost reporting is
deferred to the later profiling pass as agreed.
