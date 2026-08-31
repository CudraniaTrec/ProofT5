# Auxiliary locally available modern decoder-only control (2026-08-28)

The server already contained `/data2/x/hzc/models/qwen/Qwen3.5-9B`.  It is
reported separately from the four requested Qwen3/OLMo download candidates and
is not substituted for them.  No adaptation or parameter update was applied.

Both conditions used the frozen 67-row MBJP test split, the no-I/O target
prompts, one greedy candidate, complete-source generation, the same Java
scorer, and `hidden_tests_exposed=false`.  The F3 condition used the fixed
three synthetic Java examples (`identity`, `increment`, `isEmpty`).

| condition | pass@1 | compile errors | missing |
|---|---:|---:|---:|
| zero-shot | 16/67 | 38/67 | 0 |
| synthetic F3 | 11/67 | 44/67 | 0 |

The F3 result is therefore lower by five solved tasks in this control.  This
is an observed protocol result, not a claim about the four requested models.
The score files are `qwen35_9b_mbjp_zero_score.json` and
`qwen35_9b_mbjp_syn3_score.json` in this directory; candidate manifests record
the exact prompt and no hidden test fields.

