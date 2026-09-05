# Audited four-benchmark matrix — selected larger normal rows (2026-09-02)

This is the audit table for the selected larger models whose current benchmark
artifacts are usable as comparisons, together with the frozen ordinary
T5Gemma2-2B reference and ProofT5.  The small decoder-only 2B/3B controls and
Qwen3-4B are intentionally omitted from this presentation; their score files
remain preserved in the underlying artifacts and prior audit notes.

## Inclusion rule

A row is included when MBJP (67), HumanEval-Java (16), GFG (103), and SuFu
(58) each have a score file covering the full frozen denominator, with no
missing task outputs, no ignored/interface-marker candidates, and
`hidden_tests_exposed=false` in the generation manifest.  Few-shot rows must
also use the leakage-safe train-only source (or the selected six-shot
train-only source); the legacy mixed source is not accepted even if its score
file is complete.  Runtime timeouts are not silently removed from the
denominator; they are explicitly marked in the status column.  A timeout is a
measured execution failure, not a missing cell.  Known separator-token,
empty-EOS, or non-SuFu-language failures are excluded from the formal
normal-row table below.

The Java/GFG few-shot columns use the corrected, dataset-independent synthetic
three-shot protocol (`syn3c`).  MiMo uses the complete train-only
high-information six-shot protocol in this selected table, as do the selected
larger Qwen models.  The shot count is written directly in each SuFu cell so
every value is interpretable.

## Selected larger normal-row matrix (Pass@1)

| model | MBJP zero | MBJP F3 | HumanEval-Java zero | HumanEval-Java F3 | GFG zero | GFG F3 | SuFu zero | SuFu few-shot (k) | status |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| MiMo-7B Base | 34/67 | 33/67 | 3/16 | 10/16 | 38/103 | 43/103 | 0/58 | 6/58 (k=6) | complete; six-shot SuFu has no timeout/ignored candidate |
| Qwen3-14B-Base | 42/67 | 41/67 | 14/16 | 11/16 | 50/103 | 49/103 | 0/58 | 8/58 (k=6) | complete; no missing/ignored/timeout in six-shot SuFu |
| Qwen3-30B-A3B-Base | 42/67 | 45/67 | 13/16 | 14/16 | 52/103 | 52/103 | 0/58 | 6/58 (k=6) | complete; 3 Java-GFG timeouts in old matrix; six-shot SuFu clean |
| **ordinary T5Gemma2-2B (frozen trained reference)** | **9/67†** | N/A (trained) | **2/16†** | N/A (trained) | **14/103†** | N/A (trained) | **18/58†** | N/A (trained) | frozen paper-comparison checkpoints; not a decoder-only zero/few-shot run |
| **ProofT5 (ours, frozen trained model)** | **17/67** | **N/A (trained)** | **8/16** | **N/A (trained)** | **31/103** | **N/A (trained)** | **25/58** | **N/A (trained)** | frozen trained reference |

All cells above are filled with a value or an explicit not-applicable label;
there are no unreported benchmark cells in this selected table.  ProofT5 is a trained
encoder-decoder checkpoint rather than a zero/few-shot decoder-only control,
so its few-shot cells are explicitly marked as not applicable rather than
treated as missing data.  The daggered ordinary T5Gemma2 values are its frozen
trained-model test results, not zero-shot decoder-only results; the corresponding
few-shot cells are therefore not applicable.

### Qwen3-32B protocol correction

The earlier Qwen3-32B Java files are not used in this matrix: they were
generated with `completion_mode=full_source` while the Base-model prompt had
already supplied a class prefix, so most outputs were only TODO/closing-brace
fragments and the scores collapsed to zero.  Fresh additive runs use the same
`prefix_completion` interface as the other Qwen Base rows, keep the frozen
denominators, and retain measured timeout candidates.  The adopted corrected
score files are `qwen3_32b_prefix_{mbjp,he,gfg}_{zero,f3}_20260902_score.json`.

## Selected six-shot SuFu follow-up

The following are additive, stricter `full_stdout` Full Output Pass@1 results
using six train-only demonstrations and one greedy candidate on all 58 tasks.
MiMo completes in about 456.8 s (7.9 s/task; 394.9 output tokens/task) with no
missing or timed-out candidate:

| model | SuFu six-shot Full Output Pass@1 | result-only diagnostic | compile errors |
|---|---:|---:|---:|
| MiMo-7B Base | **6/58 (10.34%)** | 24/58 | 25/58 |
| Qwen3-14B-Base | **8/58 (13.79%)** | 25/58 | 25/58 |
| Qwen3-30B-A3B-Base | **6/58 (10.34%)** | 16/58 | 22/58 |

These six-shot rows do not replace the common F3 columns above.  The complete
protocol and score files are documented in
`SUFU_MULTISHOT_BALANCED_RESULTS_20260902.md`.

The removed Qwen3-32B and Qwen3.6-27B diagnostic score files remain preserved
under this artifact directory and are not used in the consolidated comparison.

### Java zero-shot/few-shot prompt audit

For the Java prefix-completion controls, zero-shot and F3 use the same target
prompt suffix byte-for-byte.  F3 only prepends three fixed synthetic Java
files (898 extra characters for every target); neither condition serializes
the target `test` harness or reference `code`.  The observed zero-versus-F3
differences are therefore not a reason to down-correct zero-shot: MiMo gains
on HumanEval/GFG but drops one MBJP task, Qwen3-30B gains on MBJP, and Qwen3-14B
and corrected Qwen3-32B show small drops on some benchmarks.  The read-only
check is `scripts/audit_java_zero_fewshot_prompt_20260902.py`; it verifies all
186 Java target prompts.

## Excluded interface-invalid rows

| model | why it is not in the normal-row table |
|---|---|
| Qwen3.8-27B | Two SuFu candidates per condition are ignored interface markers; denominator is not clean under the normal-row rule. |
| OLMo-3-1125-32B | Its older 3-shot matrix is complete, but the latest six-shot prefix check repeatedly leaves SuFu and emits Python/Java/English; no formal six-shot score is assigned. |
| Qwen3.5-9B, Qwen3.5-27B, Qwen3.5-35B-A3B, Qwen3.6-35B-A3B | Their only SuFu few-shot matrices use the legacy mixed source containing a debug-overlap row; the score files are preserved, but they are not leakage-safe formal rows. |

These exclusions preserve the underlying score JSONs and generated outputs;
they prevent an interface bug or invalid few-shot provenance from being
presented as a normal model result.  The small-control rows (including
Qwen3-4B) are omitted from this view only for scope/readability and are not
deleted.

## Audit sources

* `scripts/audit_sufu_boundary_20260902.py` checks the train-only SuFu rows,
  full 58-task coverage, manifest contract, and hidden-test guard.
* `scripts/audit_selected_sufu_k6_20260902.py` checks the three displayed
  six-shot rows for 58/58 outputs, k=6,
  train-only provenance, full-output scoring, and zero missing/ignored cells.
* `scripts/audit_qwen32_prefix_matrix_20260902.py` checks all six corrected
  Qwen3-32B Java rows for the prefix-completion contract and frozen
  denominators; timeout candidates are reported rather than discarded.
* `scripts/audit_qwen36_interface_20260902.py` records why the old Qwen3.6
  Java rows are diagnostic (thinking outputs hit the 1024-token cap without a
  closing marker) and verifies the additive prefix/no-chat smoke control.
* `scripts/audit_large_matrix_final_20260901.py` checks the larger-model 8/8
  benchmark score-file matrix and reports timeout/ignored diagnostics.
* `MASTER_COMPARISON_TABLE_HIGHINFO_SUFU_20260828.md` remains the compact
  paper-facing table; this file is the exhaustive audited appendix-style view.
