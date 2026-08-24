# T5Gemma2 comparison checkpoints

Last updated: 2026-07-31

The following two ordinary T5Gemma2 checkpoints are frozen as the baseline
checkpoints for subsequent paper-comparison tests. Unless an experiment
explicitly states otherwise, all comparisons against ordinary T5Gemma2 must use
these archived paths. Do not select a different epoch independently for a new
table or metric.

## Frozen checkpoints

| Dataset | Archived checkpoint | SHA256 (`model.safetensors`) |
|---|---|---|
| SuFu | `t5_llm/models/paper_comparison_20260731/t5gemma2-2b_sufu` | `edbabe5ce0e03f21e569ddd0d2ad62c1d8ec0017589b740c2d4dcaf989b04ea4` |
| Java/MBJP | `t5_llm/models/paper_comparison_20260731/t5gemma2-2b_mbjp` | `6bf88a87e24d9d04871b79d21af422fec015eaf8ec0c326db2f745ddbe6ae28a` |

These are independent archived copies. The original training-lineage paths are:

- SuFu:
  `t5_llm/models/t5gemma2-2b_sufu/checkpoint_sweep_steps_v3_20260730/epoch_7_step_25`
- Java/MBJP:
  `t5_llm/models/t5gemma2-2b_mbjp/checkpoint_sweep_fine_v2_20260730/epoch_16`

## Baseline results used for comparison

The execution timeout is one second. Re-evaluation with a ten-second timeout
produced the same four reported metrics.

| Dataset | Pass@1 | Pass@10 | FSP | CER |
|---|---:|---:|---:|---:|
| SuFu selected baseline | 31.03% | 41.38% | 6.19 | 59.31% |
| Java/MBJP selected baseline | 13.43% | 32.84% | 7.45 | 21.34% |

For context, the corresponding paper values are:

| Dataset | Pass@1 | Pass@10 | FSP | CER |
|---|---:|---:|---:|---:|
| SuFu paper row | 29.31% | 37.93% | 6.69 | 61.21% |
| Java/MBJP paper row | 17.91% | 35.82% | 6.99 | 15.22% |

No evaluated checkpoint reproduced all four paper values simultaneously. These
two checkpoints were selected using the previously agreed equal-column L2
distance over Pass@1 percentage points, Pass@10 percentage points, FSP, and CER
percentage points. This is a recovery choice made on the test results, not an
unbiased validation-based model-selection procedure.

## Test usage

Use the archived paths as `--checkpoint_path`:

```bash
# SuFu
--checkpoint_path t5_llm/models/paper_comparison_20260731/t5gemma2-2b_sufu

# Java/MBJP
--checkpoint_path t5_llm/models/paper_comparison_20260731/t5gemma2-2b_mbjp
```

The machine-readable version of this selection is
`t5_llm/comparison_checkpoints.json`.
