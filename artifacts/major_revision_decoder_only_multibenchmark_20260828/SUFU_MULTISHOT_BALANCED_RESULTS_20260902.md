# SuFu balanced few-shot results (2026-09-02)

This is an additive follow-up to the frozen three-shot rows.  It uses the
unchanged 58-task SuFu test split, one greedy candidate per task, and exact
`full_stdout` Pass@1 for the formal metric.  No test, expected output, or
postfix field is present in the few-shot examples.

## Selection pilots

The first ten frozen test tasks were used only to select a modest shot count
and a stable source interface.  The table reports the actual ten-task pilot
denominator; the result-only column is diagnostic and is not the formal metric.

| model / setting | Full Output | result-only | compile errors |
|---|---:|---:|---:|
| Qwen3-14B, original Balanced-6, full-source | 2/10 | 6/10 | 3/10 |
| Qwen3-14B, canonical-coverage-6, full-source | 1/10 | 6/10 | 4/10 |
| Qwen3-14B, canonical-coverage-6 + explicit full-output wording | 0/10 | 5/10 | 5/10 |
| Qwen3-30B-A3B, original Balanced-6, prefix | 0/10 | 3/10 | 4/10 |
| Qwen3-30B-A3B, canonical-coverage-6, prefix | **4/10** | **5/10** | 3/10 |
| Qwen3-30B-A3B, canonical-coverage-9, prefix | 3/10 | 4/10 | 3/10 |
| Qwen3-32B, canonical-coverage-6, prefix | 2/10 | 6/10 | 3/10 |

Canonical-coverage-6 is the six-row train-only set

```
incre-tests-synduce-constraints-sortedlist-max
incre-tests-synduce-constraints-memo-max_contains
incre-tests-synduce-constraints-sortedlist-parallel_max2
incre-tests-autolifter-dac-mts_p
incre-tests-autolifter-single-pass-is_sorted
incre-tests-fusion-tupling-page1
```

It covers target-bearing plain-list/CList/TreeMemo programs as well as
Autolifter `dac`/`single_pass` and Fusion tree syntax.  Every row is from the
sanitized train-only file and independently parses/type-checks.  Nine shots
were rejected because the pilot dropped from 4/10 to 3/10; 12 shots were not
needed.  This confirms that a larger context is not automatically better for
exact Full Output: declaration-order copying and missing target definitions
are common failure modes.
Qwen3-32B was also checked at six shots; its 2/10 strict pilot was below the
30B-A3B result, but the requested complete run was nevertheless executed for
matrix completeness.

## Complete selected evaluation

| model | few-shot condition | Full Output Pass@1 | result-only diagnostic | compile errors |
|---|---|---:|---:|---:|
| MiMo-7B Base | canonical-coverage-6, full-source | **6/58 (10.34%)** | 24/58 (41.38%) | 25/58 |
| Qwen3-14B-Base | Balanced-6, full-source | **8/58 (13.79%)** | 25/58 (43.10%) | 25/58 |
| Qwen3-30B-A3B-Base | canonical-coverage-6, prefix | **6/58 (10.34%)** | 16/58 (27.59%) | 22/58 |
| Qwen3-32B | canonical-coverage-6, prefix | **5/58 (8.62%)** | 14/58 (24.14%) | 21/58 |
| Qwen3.6-27B | canonical-coverage-6, prefix | **8/58 (13.79%)** | 19/58 (32.76%) | 18/58 |

Strict Full Output solved task IDs are MiMo-7B:
`[8, 16, 20, 23, 39, 45]`; Qwen3-14B:
`[4, 5, 23, 34, 36, 41, 45, 50]`; Qwen3-30B-A3B:
`[0, 2, 7, 8, 11, 16]`.  These lists come directly from the scorer JSONs,
not from result-only matching.

Qwen3-32B solved IDs are `[7, 8, 11, 16, 23]`; Qwen3.6-27B solved IDs are
`[0, 2, 7, 8, 11, 13, 16, 39]`.  Its generation
span was 570.6 s (9.8 s/task; 484.6 output tokens/task) on the local bf16
runner.  The previously completed Qwen3-32B six-shot row (5/58 strict,
14/58 result-only) is included in this complete evaluation record but omitted
from the compact headline table because it is a near-duplicate of the
30B/27B scale points.

The MiMo generation span was 456.8 s (7.9 s/task; 394.9 output tokens/task).
The saved trajectory metadata also records wall-clock generation cost.  The
Qwen3-14B run took 768.8 s total (13.3 s/task on average; 478.5 output tokens
per task), Qwen3-30B-A3B took 306.0 s total (5.3 s/task; 129.6 output
tokens/task), and Qwen3-32B took 553.3 s total (9.5 s/task; 210.0 output
tokens/task).  These are generation-only timings from the local bf16 runner;
SuFu execution/scoring time is separate.

Formal evaluation uses the bold exact Full Output numbers.  The result-only
column shows how many additional candidates were semantically executable but
did not reproduce the complete declaration transcript; it must not be put in
the paper's Pass@1 table.  The Qwen3.6-27B row is a valid SuFu-only
prefix/no-chat run; it does not repair or replace that model's incompatible
Java full-source matrix.

## OLMo-3 check

OLMo-3-1125-32B was checked with canonical-coverage-6/prefix.  The first seven
outputs copied Python/Java or English code after the public SuFu prefix (with
no stable SuFu continuation), and the run was stopped as an interface
diagnostic rather than spending the remaining GPU time on a known-invalid
format.  Its earlier full-source
zero/F3 rows remain archived diagnostics.  It is not assigned a fabricated
formal score in this follow-up.

The archived Qwen3.5/3.6/3.8 rows are not rerun here even though several local
snapshots are available: they are highly correlated Qwen-family variants and
would add redundant rows to the compact comparison.  Their earlier three-shot
matrices remain unchanged in the archived large-model artifacts.  Qwen3-32B's
six-shot result is complete and is included above; it is only omitted from the
compact headline follow-up.

## Reproduction

Generated candidates are under
`Utils/output/sufu_original_test_t5gemma2_20260731_test_ans/` with tags
`sufu_mimo_canonical6_full_final_20260902`,
`sufu_q14b_balanced6_full_final_20260902`,
`sufu_q30b_canonical6_prefix_final_20260902`,
`sufu_q32b_canonical6_prefix_final_20260902`, and
`sufu_q36_27b_canonical6_prefix_final_20260902`.

The exact scorer commands are:

```bash
uv run --project . score_sufu_no_write.py \
  --task sufu_original_test_t5gemma2_20260731 --split test \
  --output_tag sufu_mimo_canonical6_full_final_20260902 \
  --pass_at_k 1

uv run --project . score_sufu_no_write.py \
  --task sufu_original_test_t5gemma2_20260731 --split test \
  --output_tag sufu_q14b_balanced6_full_final_20260902 \
  --pass_at_k 1

uv run --project . score_sufu_no_write.py \
  --task sufu_original_test_t5gemma2_20260731 --split test \
  --output_tag sufu_q30b_canonical6_prefix_final_20260902 \
  --pass_at_k 1

uv run --project . score_sufu_no_write.py \
  --task sufu_original_test_t5gemma2_20260731 --split test \
  --output_tag sufu_q32b_canonical6_prefix_final_20260902 \
  --pass_at_k 1

uv run --project . score_sufu_no_write.py \
  --task sufu_original_test_t5gemma2_20260731 --split test \
  --output_tag sufu_q36_27b_canonical6_prefix_final_20260902 \
  --pass_at_k 1
```

The corresponding JSON reports are
`mimo_canonical6_full_final_20260902_score.json`,
`q14b_balanced6_full_final_20260902_score.json` and
`q30b_canonical6_prefix_full_final_20260902_score.json`, and
`q36_27b_canonical6_prefix_full_final_20260902_score.json`, and
`q32b_canonical6_prefix_full_final_20260902_score.json`;
the separate
`*_results_final_20260902_score.json` files use `--compare_test_results_only`
and are diagnostics only.  The read-only completeness check for these five
six-shot rows is `scripts/audit_selected_sufu_k6_20260902.py`.
