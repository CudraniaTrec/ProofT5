# RQ3 formal data package (2026-09-03)

This file is the paper-facing index for the reliability-baseline results.  It
freezes the existing result trees and does not replace any checkpoint, output,
or score file.  The primary metric is task-level **Pass@1**; the existing
Pass@10 values are retained as a compatibility/appendix metric only.

## Reproduction status and scope

The two external baselines reproduce the core mechanisms described by their
original papers, with a documented Java/MBJP task adapter:

* **Repilot:** the runner uses the modified Eclipse JDT completion endpoint
  (`newCompletion`) as the feasibility oracle, with the upstream trivial
  bypass for punctuation/Java keywords, empty completion rejected, and null or
  otherwise unknown completion accepted.  The IDE+safe-ACTIVE row additionally
  enables the completion capability set and treats ACTIVE proposals as
  affirmative hints, falling back to the same JDT policy when a proposal is
  incomplete.  It does not import SynCode.  This is a faithful Repilot/JDT
  adaptation to MBJP, not an unmodified Defects4J repair-CLI run, because the
  original tool is tied to its Defects4J project wrapper and repair interface.
* **SynCode:** the Java adapter performs incremental CFG/LALR grammar masking
  on the generated suffix and uses proposal-preserving rejection in the
  matched setting.  The paper-facing ``+ javac`` row is the predeclared
  compile-safe portfolio: it compares the ordinary and constrained arms and
  retains the ordinary candidate unless standalone ``javac`` rejects it and
  the constrained candidate compiles.  It must therefore be labelled as a
  **SynCode Java adaptation/compile-safe portfolio**, not as an unmodified
  SynCode benchmark result.  SynCode supplies syntax constraints, not Java
  type or semantic correctness.

These descriptions are consistent with the [Repilot paper](https://arxiv.org/html/2309.00608)
and its [official implementation](https://github.com/ise-uiuc/Repilot).  The
original SynCode implementation and the Java adapter lock are documented in
`baselines/java_baselines/README.md` and `UPSTREAM_LOCK.json`.

## Common formal protocol

All rows in the reliability comparison use the same frozen T5Gemma2-2B
paper-recovery checkpoint and the same MBJP test contract:

| Item | Frozen setting |
|---|---|
| Benchmark | MBJP Java subset, held-out test split, 67 tasks |
| Candidate budget | 10 candidates/task (670 candidate slots) |
| Prompt | exact raw benchmark Java prefix; only the unknown suffix is generated |
| Generation | bf16, `max_input_tokens=1024`, `max_new_tokens=1024`, greedy rank 0 plus fixed-seed sampling, temperature 0.8, top-k 50, top-p 0.95 |
| Seed | 273567 (global task/rank-derived schedule) |
| Selection isolation | no benchmark tests are exposed during generation, pruning, or repair; hidden tests are used only by the authoritative scorer |
| Compilation gate | OpenJDK 17, 10 s candidate timeout; standalone `javac` where the method specifies a gate |
| Metric | Pass@1 is the main result; Pass@10 is retained for the existing appendix table. CER is computed over returned candidates (unfilled rejection slots are fail-closed). |

## Frozen correctness results

Counts are solved tasks over 67 and compile errors over 670 returned candidate
slots.  Percentages are included to make direct manuscript transcription
unambiguous.

| Paper-facing row | Pass@1 | Pass@10 (appendix) | CER | Interpretation | Authoritative score |
|---|---:|---:|---:|---|---|
| T5Gemma2-2B ordinary matched control | 10/67 (14.93%) | 23/67 (34.33%) | 122/670 (18.21%) | Frozen decoder control | [`ordinary_paper_recovery_matched_sampling.json`](../major_revision_mbjp_baselines_20260825/scores/ordinary_paper_recovery_matched_sampling.json) |
| + rejection sampling (`javac`) | 10/67 (14.93%) | 24/67 (35.82%) | 0/618 returned (0.00%) | Four 10-draw rounds; 52 slots on six tasks remain unfilled and count as failures | Existing values in `tosem/paper/chapters/evaluation.tex` and rejection-sampling output manifests |
| + SynCode, proposal-preserving diagnostic | 10/67 (14.93%) | 23/67 (34.33%) | 122/670 (18.21%) | Core grammar adaptation alone preserves the ordinary solved sets | [`syncode_proposal_preserving.json`](../major_revision_mbjp_baselines_20260825/scores/syncode_proposal_preserving.json) |
| + SynCode, compile-safe portfolio (reported row) | 10/67 (14.93%) | 24/67 (35.82%) | 73/670 (10.90%) | Ordinary/constrained two-arm portfolio plus standalone `javac`; not unmodified SynCode | [`syncode_compile_safe.json`](../major_revision_mbjp_baselines_20260825/scores/syncode_compile_safe.json) |
| + Repilot/JDT, upstream-faithful policy | 10/67 (14.93%) | 23/67 (34.33%) | 112/670 (16.72%) | Modified JDT `newCompletion`; no ACTIVE insertion and no SynCode | [`repilot_sound_default_rerun.json`](../major_revision_mbjp_baselines_20260825/scores/repilot_sound_default_rerun.json) |
| + Repilot/JDT, IDE + safe ACTIVE | 10/67 (14.93%) | 23/67 (34.33%) | 112/670 (16.72%) | Best-effort IDE capabilities, safe affirmative ACTIVE hints, proposal memoization; same frozen output distribution | [`repilot_ide_active_safe_b10_score_20260903.json`](repilot_ide_active_safe_b10_score_20260903.json) |
| + iterative compiler repair | 8/67 (11.94%) | 17/67 (25.37%) | 83/670 (12.39%) | At most two `javac`-diagnostic repair rounds; no benchmark tests during repair | [`iterative_mbjp.json`](../major_revision_mbjp_baselines_20260825/scores/iterative_mbjp.json) |
| ProofT5 (trained reference) | 17/67 (25.37%) | 29/67 (43.28%) | 3/670 (0.45%) | Trained representation-aware reference; not a frozen-baseline pruning run | [`prooft5_frozen.json`](../major_revision_mbjp_baselines_20260825/scores/prooft5_frozen.json) |

The rejection-sampling row is recorded in the manuscript as a by-construction
zero-CER result; its score is not a new generation distribution and should not
be compared as if it had returned 670 candidates.  The proposal-preserving
SynCode row is kept for auditability, while the compile-safe portfolio is the
stronger row used in the RQ3 comparison table.

For the IDE+safe-ACTIVE Repilot row, the linked ``*_score`` file is the
rank-0 Pass@1 scorer (and consequently reports 9/67 rank-0 compile errors),
whereas the linked ``*_pass10_score`` file is the 10-candidate aggregate used
for the table's 112/670 CER and 23/67 Pass@10.  The two files share the same
670 candidate tree.

## Repilot strengthening audit

The full IDE+safe-ACTIVE rerun completed all 67 x 10 candidate files and
returned the same 10/67 and 23/67 task sets as the upstream-faithful row.  It
made 17,963 JDT queries and reused 9,736 memoized proposal states.  The
training replay accepted all 58,045 tokens in 608 known-correct programs with
zero false-pruned programs.  The full-run record is:

* score: [`repilot_ide_active_safe_b10_score_20260903.json`](repilot_ide_active_safe_b10_score_20260903.json)
* Pass@10 audit score: [`repilot_ide_active_safe_b10_pass10_score_20260903.json`](repilot_ide_active_safe_b10_pass10_score_20260903.json)
* method report: [`REPILOT_IDE_ACTIVE_SAFE_RESULTS_20260903.md`](REPILOT_IDE_ACTIVE_SAFE_RESULTS_20260903.md)
* safety audit: [`REPILOT_STRENGTHENING_AUDIT_20260903.md`](REPILOT_STRENGTHENING_AUDIT_20260903.md)

The accuracy-first pilots (every-token JDT, proactive insertion, replacement
edit handling, temperature changes, and SynCode full-vocabulary fallback)
were deliberately kept separate.  None exceeded 2/10 Pass@1 on the matched
10-task pilot, so none is promoted to a paper-facing full-benchmark result:
[`EFFECT_FIRST_RERUN_RESULTS_20260903.md`](EFFECT_FIRST_RERUN_RESULTS_20260903.md).

## Manuscript mapping

The formal rows and their interpretation are already present in
`tosem/paper/chapters/evaluation.tex`, subsection
“RQ3: Reliability-Oriented and Modern Decoder-Only Baselines”.  The existing
cost table remains an auxiliary record; it is not used to claim an accuracy
improvement.  No frozen checkpoint, score tree, or headline result is
overwritten by this package.

For the final paper, keep the following wording discipline:

1. Call the Repilot row “Repilot/JDT (upstream-faithful)” and the second row
   “Repilot/JDT (IDE + safe ACTIVE)”.
2. Call the stronger SynCode row “SynCode Java adaptation + compile-safe
   portfolio”; do not call it a literal upstream SynCode result.
3. State that all external reliability methods operate on the output
   distribution of the frozen checkpoint.  Their unchanged Pass@1 is a
   measured result, not a failed reproduction.
4. Keep ProofT5 in a separate trained-reference row; it is not an apples-to-
   apples zero-shot decoder-only baseline.
