# SuFu realistic train-like F3 results (2026-08-28)

These runs are additive to the frozen comparison table.  The examples are
the three fixed training-split task IDs documented in
`SUFU_REALISTIC_TRAINLIKE_THREESHOT_SPEC.md`; no test, output, or postfix
field is sent to a model.  The capability-oriented target protocol uses
full-source prompting with the complete task description, public prefix, rich
demonstrations, and explicit SuFu guidance.  The earlier source-prefix/no-chat
results are retained as a restricted-format control.

| model | scope | pass@1 | compile errors | missing |
|---|---|---:|---:|---:|
| CodeGemma-2B PT | 10-task pilot | 1/10 | 9/10 | 0 |
| CodeGemma-2B PT | full test (58) | 1/58 | 51/58 | 0 |
| MiMo-7B Base | 10-task pilot | 3/10 | 1/10 | 0 |
| MiMo-7B Base | full test (58) | 3/58 | 18/58 | 0 |
| MiMo-7B Base | high-information full-source pilot | 4/10 | 4/10 | 0 |
| MiMo-7B Base | high-information full test (58) | 8/58 | 33/58 | 0 |
| MiMo-7B Base | high-information pilot, old example IDs | 0/10 | 4/10 | 0 |

## Full-model SuFu matrix

The final high-information full-test rows are:

| model | zero-shot pass@1 | 3-shot pass@1 | zero-shot compile errors | 3-shot compile errors |
|---|---:|---:|---:|---:|
| CodeGemma-2B PT | 0/58 | 0/58 | 58/58 | 58/58 |
| Gemma-2-2B Base | 0/58 | 0/58 | 58/58 | 58/58 |
| StarCoder2-3B Base | 0/58 | 1/58 | 43/58 | 56/58 |
| SmolLM3-3B Base | 0/58 | 0/58 | 0/58* | 0/58* |
| Granite-3.3-2B Base | 0/58 | 0/58 | 53/58 | 58/58 |
| Qwen3-4B Base | 0/58 | 5/58 | 47/58 | 41/58 |
| MiMo-7B Base | 0/58 | 8/58 | 43/58 | 33/58 |

All rows have 58 generated candidate files and no missing candidates.  `*`
means that SmolLM3 immediately emitted EOS/empty text for every task, so the
scorer did not label these empty strings as compilation errors; those cells
are interface failures rather than successful compilations.

The CodeGemma success is task index 5; MiMo succeeds on indices 2, 5, and 8
in both the pilot and full run.  The matching output directories and score
JSON files record the dataset hash, example IDs/fingerprint, model path,
`hidden_tests_exposed=false`, and generation timings.  The runner also now
removes a repeated demonstration stream after a generated `main`, with unit
tests covering this contamination case.

For the restricted prefix runs, the identical pilot/full hit sets are
expected, not reused scoring: both runs use one greedy candidate
(`seed=273567`) and the pilot is exactly indices
0--9.  Re-scoring the first ten files from the full output gives MiMo 3/10
with solved IDs `[2, 5, 8]`; byte-level hashes of all ten pilot/full
candidates match.  Thus that pilot is a deterministic smoke check and should
not be treated as an independent test estimate.

The high-information full-source run is a separate capability estimate.  Its
8/58 score is directly comparable to the earlier 9/58 full-source diagnostic
at the protocol level, while using the new, more realistic demonstrations and
explicit guidance.  It should replace the restricted prefix row as the main
SuFu decoder-only comparison once the remaining model rows are rerun.

As a small prompt-composition check, the same high-information runner with
the three example IDs used by the earlier 9/58 run scored 0/10 on the first
ten tasks.  This confirms that the old 9/58 value cannot be attributed to the
new guidance alone; demonstration selection and decoding protocol both matter.

For comparison, the old hand-written toy/full-source diagnostic produced
0/58 for CodeGemma and is not mixed with this row.  The train-like protocol
therefore fixes the demonstrated prompt-format failure, but it does not make
a 2B general code model competitive with a trained SuFu model; that remaining
gap is a capability result, not evidence of test leakage.
