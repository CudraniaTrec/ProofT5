# Qwen2.5-Coder-3B causal-DSL comparison (2026-08-25)

This directory records the modern decoder-only MBJP comparison for Major
Revision RQ3.  Both arms use Qwen2.5-Coder-3B Base, the approved 673-program
clean Java training boundary, the frozen ProofT5 DSL vocabulary/targets, and
the same 67 MBJP test tasks with ten beams.  This is a decoder-only extension,
not the ordinary T5Gemma2 control used by SynCode, Repilot, and iterative
refinement.

The ordinary arm fully fine-tunes the causal model.  The CoqView arm starts
from the test-free selected ordinary checkpoint, freezes the backbone and DSL
embedding/output table, and trains only a zero-initialized Coq projection and
unit-initialized scalar gate at 1e-5.  This initialization exactly preserves
the ordinary logits before continuation while allowing a first-step gradient
through the projection.  Only the causally available CoqView state is exposed
at the position predicting the next DSL token.

Checkpoint candidates were fixed at epochs 5, 10, 15, 20, and final.  Both
arms selected `final` using global token-weighted training loss only, before
either arm generated MBJP test output:

- ordinary: loss 0.0179774656, SHA-256
  `bac0aab927838b2415fa84b23f9968ef11793225034b0428c55f91523ddfca15`;
- CoqView: loss 0.0206995961, SHA-256
  `2361abcd76a878a2f4a182201dc26980682c70b8f1490dbec58f7077adf9f0de`.

The Qwen evaluation pickle is necessarily not byte-identical to the raw
benchmark JSON because natural-language inputs are retokenized, task IDs are
normalized, and reference Java is formatting-cleaned.  The scorer therefore
fails closed on a narrower, scoring-relevant equivalence contract: all 67
rows must preserve `benchmark`, `original_split`, and the complete Java hidden
test harness in identical order.  The result JSON records that verification,
both source hashes, checkpoint hash, decoder settings, candidate-tree hash,
missing outputs, compilation errors, and solved-task IDs.

Earlier adapter diagnostics are retained for audit but are not formal result
arms.  `protocol.json` explains why the zero-gate 1e-6, feature-LR 1e-4, and
full-model continuation trials were rejected before test generation.  Formal
scores are written to `plain_mbjp_score.json` and
`coqview_mbjp_score.json` after complete generation and fail-closed scoring.

The complete ordinary result is 26/67 pass@1 and 39/67 pass@10, with 57/670
compilation errors and no missing or timed-out candidates.  It is materially
stronger in absolute functional accuracy than both the matched ordinary
T5Gemma2 control (10/23) and the current ProofT5 T5Gemma2 result (17/29).  The
paper must report this architecture/training distinction and should use the
ordinary-versus-CoqView Qwen pair to test whether the proposed representation
adds value on top of the stronger decoder-only backbone; it must not claim
that the T5Gemma2 ProofT5 row is universally best across architectures.

The complete CoqView result is 25/67 pass@1 and 41/67 pass@10. It has four
compilation errors among 643 materialized candidates, one Java test timeout,
and 27 empty beam-budget positions. All 67 problems have a top-1 output. The
empty positions are genuine constrained-search exhaustion, not missing
shards: per-problem candidate counts are 10 for 60 tasks and 9, 8, 6, 6, 6,
5, and 3 for the other seven, exactly matching their beam-score metadata.

Relative to ordinary Qwen, CoqView loses one pass@1 task and gains two net
pass@10 tasks. The paired changes are 0 gains versus 1 loss at pass@1
(exact McNemar p=1.0) and 5 gains versus 3 losses at pass@10 (p=0.7265625).
Thus the controlled result supports a large compilability improvement and a
small, statistically non-significant pass@10 increase, not a stable functional
gain on the stronger backbone.

Observed wall time to the last problem output was 509.12 seconds for ordinary
Qwen and 8,249.50 seconds for CoqView. The latter used dynamically expanded
fixed-index shards because real token-level `coqc` calls dominated while GPUs
were mostly idle. It is an end-to-end completion time, not a compute-matched
cost: aggregate GPU-worker/CPU/checker process-seconds were not instrumented.
See `evaluation_orchestration.json` for the exact boundary and limitation.
