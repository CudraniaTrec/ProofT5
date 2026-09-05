# Master four-benchmark comparison — pass@1 only (2026-09-02)

All entries are `solved/total` and report **pass@1 only**. Java `F3` means
three-shot prompting with the fixed synthetic examples. The SuFu few-shot
column uses the leakage-safe six-shot train-only condition for the displayed
decoder-only rows. Every decoder-only row uses one greedy candidate. The
ordinary T5Gemma2 and ProofT5 rows are frozen trained-model references, so
their few-shot cells are not applicable.

For the exhaustive audit view containing every leakage-safe complete row, see
`MASTER_FOUR_BENCHMARK_NORMAL_MODELS_20260902.md`.  This file remains the
compact paper-facing comparison.

To keep the headline table readable, it retains MiMo-7B and two Qwen3 scale
points (14B dense and 30B-A3B Base), together with the ordinary T5Gemma2-2B
reference and ProofT5.  Exploratory and interface-diagnostic Qwen rows remain
archived and are not part of this consolidated table.

| model | MBJP zero (p@1) | MBJP F3 (p@1) | HumanEval-Java zero (p@1) | HumanEval-Java F3 (p@1) | GFG zero (p@1) | GFG F3 (p@1) | SuFu zero (p@1) | SuFu few-shot (p@1; k=6) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| MiMo-7B Base | 34/67 | 33/67 | 3/16 | 10/16 | 38/103 | 43/103 | 0/58 | **6/58** |
| Qwen3-14B-Base | 42/67 | 41/67 | 14/16 | 11/16 | 50/103 | 49/103 | 0/58 | **8/58** |
| Qwen3-30B-A3B-Base | 42/67 | 45/67 | 13/16 | 14/16 | 52/103 | 52/103 | 0/58 | **6/58** |
| **ordinary T5Gemma2-2B (frozen trained reference)** | **9/67†** | N/A (trained) | **2/16†** | N/A (trained) | **14/103†** | N/A (trained) | **18/58†** | N/A (trained) |
| **ProofT5 (ours, frozen trained model)** | **17/67** | N/A | **8/16** | N/A | **31/103** | N/A | **25/58** | N/A |

The MiMo and selected Qwen SuFu cells are complete leakage-safe six-shot
train-only runs; their zero-shot cells are complete boundary-only runs. No
hidden tests or expected outputs are sent to any model. The full audit,
including compilation-error and interface-failure rates, is in
`SUFU_REALISTIC_TRAINLIKE_RESULTS.md` and
`MASTER_FOUR_BENCHMARK_NORMAL_MODELS_20260902.md`.

The Java columns are copied from the audited decoder-only runs. Java F3 remains
intentionally low-information; SuFu six-shot uses the richer train-only
demonstrations. The ordinary T5Gemma2 cells use the frozen paper-comparison
checkpoints documented in `t5_llm/comparison_checkpoints.json` and are not
zero-shot decoder-only measurements; the dagger marks these trained-model
reference values. Historical score JSONs may retain
additional candidates, but they are not used in this comparison.

The separate six-shot SuFu protocol and its diagnostic score files remain in
`SUFU_MULTISHOT_BALANCED_RESULTS_20260902.md`; removed Qwen3-32B and
Qwen3.6-27B rows are not folded into this table.

## Completion audit and reproducibility

The selected larger candidates (MiMo-7B Base, Qwen3-14B-Base, and
Qwen3-30B-A3B-Base) have complete, leakage-safe SuFu conditions.  The removed
Qwen3-32B/Qwen3.6-27B and OLMo-3 checks remain archived as diagnostics and are
not formal rows.  Exploratory Qwen3.5/Qwen3.8 checkpoints remain outside the
compact table.  The
read-only audit is
`scripts/audit_large_matrix_final_20260901.py`; it checks all 8 score JSONs
per row, the frozen denominator (MBJP 67, HumanEval-Java 16, GFG-v13 103,
SuFu 58), and missing outputs.  The generated-candidate directories contain
one greedy candidate for every task.

Two explicit failure annotations remain part of the evidence rather than being
silently dropped: Qwen3-30B-A3B-Base has three GFG timeout candidates in total
(one zero-shot and two 3-shot), and OLMo-3-1125-32B has two GFG timeouts in each
condition.  Qwen3.8-27B emits two SuFu interface-marker candidates in each
condition; these are counted as failures (0/58), while all 58 task IDs were
attempted.  No hidden tests, expected outputs, or test-split examples were
included in any prompt.

The completed archived Qwen3.5/Qwen3.8 and larger-model score files follow the naming
pattern `<slug>_<benchmark>_<zero|f3>_score.json` in this directory.  The
machine-readable report is produced with:

```text
cd scripts && /data2/x/hzc/.uv-envs/prooft5-t5gemma-py313/bin/python report_large_matrix_20260901.py
```
