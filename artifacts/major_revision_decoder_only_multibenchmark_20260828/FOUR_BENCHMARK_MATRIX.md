# Four-benchmark decoder-only matrix (2026-08-28)

This file separates the completed controls from conditions that have not yet
been run. Counts are `solved/total`; `p1/p10` means pass@1/pass@10. A dash is
not a zero: it means that the condition is not available in the current
artifacts. The four test sets are MBJP (67), HumanEval-Java v15 (16),
TransCoder-GFG v13 (103), and SuFu (58).

## Decoder-only zero-shot

The first five rows use the 2026-08-27 one-candidate Java/GFG/SuFu pilots and
the existing ten-candidate MBJP pass@1/pass@10 controls. MiMo's MBJP row is a
valid3 one-candidate pilot, so its p10 is unavailable. Qwen3 uses its existing
full-source chat protocol.

| model | MBJP p1/p10 | HumanEval p1 | GFG p1 | SuFu p1 |
|---|---:|---:|---:|---:|
| CodeGemma-2B PT | 29/48 | 5/16 | 40/103 | 0/58 |
| Gemma-2-2B Base | 23/43 | 3/16 | 27/103 | 0/58 |
| StarCoder2-3B Base | 21/50 | 5/16 | 39/103 | 0/58 |
| SmolLM3-3B Base | 28/42 | 6/16 | 33/103 | 0/58 |
| Granite-3.3-2B Base | 24/41 | 6/16 | 26/103 | 0/58 |
| Qwen3-4B Base | 34/60 | 8/16 | 25/103 | 0/58 |
| MiMo-7B Base | 34/— | 3/16 | 38/103 | 0/58 |

## New minimal-information 1-shot

These are all one greedy candidate per task. The few-shot context is one
synthetic Java skeleton generated in the runner; it contains no task, answer,
test, or I/O information. Therefore p10 is not defined for these runs.

| model | MBJP p1 | HumanEval p1 | GFG p1 | SuFu p1 |
|---|---:|---:|---:|---:|
| CodeGemma-2B PT | 28/67 | 5/16 | — | — |
| Gemma-2-2B Base | 21/67 | 3/16 | — | — |
| StarCoder2-3B Base | 22/67 | 4/16 | — | — |
| SmolLM3-3B Base | 25/67 | 6/16 | — | — |
| Granite-3.3-2B Base | 27/67 | 7/16 | — | — |
| Qwen3-4B Base | 15/67 | 8/16 | — | — |
| MiMo-7B Base | 30/67 | 9/16 | — | — |

Relative to the zero-shot references, the first five models change by −1 to
+3 MBJP tasks and −1 to +1 HumanEval tasks. MiMo changes by −4 MBJP tasks and
+6 HumanEval tasks; Qwen3 changes by −19 MBJP tasks and 0 HumanEval tasks.
These are protocol effects, not hidden-test exposure.

## Existing full 3-shot results

This is a different condition from the minimal 1-shot control. The examples
are sanitized train rows with task/source information (but no tests or I/O
examples). Only the following full 3-shot runs currently exist:

| model | MBJP p1/p10 | HumanEval p1 | GFG p1 | SuFu p1 |
|---|---:|---:|---:|---:|
| CodeGemma-2B PT | 33/45 | — | — | — |
| Gemma-2-2B Base | 30/41 | — | — | — |
| StarCoder2-3B Base | 28/47 | — | — | — |
| SmolLM3-3B Base | 31/47 | — | — | — |
| Granite-3.3-2B Base | — | — | — | — |
| Qwen3-4B Base | — | — | — | — |
| MiMo-7B Base | — | 12/16 | 42/103 | 0/58 prefix; 9/58 full-source |

All non-MBJP full 3-shot rows above use one candidate, so their pass@10 is not
available. The 3-shot MBJP rows are retained in the frozen 2026-08-26
artifact; they must not be combined with the minimal 1-shot rows as if they
were one protocol.

## Frozen ProofT5 comparison

The authoritative major-revision table uses ten candidates and reports both
pass@1 and pass@10. This row is not a decoder-only zero/few-shot control;
ProofT5 is the trained representation model.

| benchmark | ProofT5 (ours) p1/p10 |
|---|---:|
| MBJP (67) | **17/29** |
| HumanEval-Java v15 (16) | **8/9** |
| TransCoder-GFG v13 (103) | **31/48** |
| SuFu (58) | **25/29** |

The ProofT5 rows are frozen in
`docs/MAJOR_REVISION_FINAL_PACKAGE_20260824.md` and
`tosem/paper/chapters/evaluation.tex`. The decoder-only score JSONs and the
minimal-prompt protocol are in the other files in this directory.

## Corrected complete-task three-shot matrix

The all-model Java F3 matrix is now complete under the corrected protocol:
three fixed, benchmark-shaped but dataset-independent Java tasks, one greedy
candidate per test task. The authoritative values and score-file manifests are
in `MASTER_COMPARISON_TABLE.md`; the compact matrix is:

| model | MBJP p1 | HumanEval-Java p1 | GFG p1 |
|---|---:|---:|---:|
| CodeGemma-2B PT | 30/67 | 7/16 | 44/103 |
| Gemma-2-2B Base | 27/67 | 6/16 | 34/103 |
| StarCoder2-3B Base | 29/67 | 5/16 | 38/103 |
| SmolLM3-3B Base | 33/67 | 8/16 | 37/103 |
| Granite-3.3-2B Base | 25/67 | 6/16 | 28/103 |
| Qwen3-4B Base | 33/67 | 9/16 | 45/103 |
| MiMo-7B Base | 33/67 | 10/16 | 43/103 |

SuFu remains `N/A` for this Java F3 protocol. Filling that cell would require
a separate SuFu-native set of three complete synthetic tasks and must not reuse
the old dataset-derived SuFu examples. The earlier empty-skeleton and ordinary
train-row few-shot sections above remain diagnostics only.
