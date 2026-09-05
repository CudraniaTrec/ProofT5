# SuFu realistic train-like F3 results (audit and replacement, 2026-09-02)

The first rows below are historical diagnostics from the 2026-08-28 mixed
few-shot source.  A provenance audit found one debug-overlap/test example in
that source, so those F3 values are not paper-facing.  The authoritative rows
are the train-only replacement section at the end of this file.  All runs are
additive to the frozen comparison table.  The capability-oriented target
protocol uses full-source prompting with the complete task description, public
prefix, rich demonstrations, and explicit SuFu guidance.

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

The historical high-information full-test rows are:

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

The high-information full-source run is a separate capability estimate.  These
mixed-source values are retained only for diagnosing the original prompt
format; they must not replace the train-only row in the main comparison.

As a small prompt-composition check, the same high-information runner with
the three example IDs used by the earlier 9/58 run scored 0/10 on the first
ten tasks.  This confirms that the old 9/58 value cannot be attributed to the
new guidance alone; demonstration selection and decoding protocol both matter.

For comparison, the old hand-written toy/full-source diagnostic produced
0/58 for CodeGemma and is not mixed with this row.  The train-like protocol
therefore fixes the demonstrated prompt-format failure, but it does not make
a 2B general code model competitive with a trained SuFu model; that remaining
gap is a capability result, not evidence of test leakage.

## Boundary-corrected pass@1 rerun (2026-09-02; superseded F3 source)

The original 2026-08-28 full-source prompts omitted the completion label after
the target block.  `run_decoder_only_sufu.py` now appends that boundary, and
the following additive runs use one greedy candidate, a 2048-token cap, and
the frozen 58-task split.  A later provenance audit found that one of the
three examples (`incre-tests-synduce-list-last`) was a debug-overlap row from
the test split.  These F3 scores are retained as diagnostics, not
paper-facing results; the train-only replacement below is authoritative.
Existing directories and score files were not overwritten.

| model | zero-shot pass@1 | 3-shot pass@1 | zero compile errors | 3-shot compile errors | interface observation |
|---|---:|---:|---:|---:|---|
| CodeGemma-2B PT | 0/58 | 0/58 | 58/58 | 58/58 | file-separator token dominates |
| Gemma-2-2B Base | 0/58 | 1/58 | 27/58 | 53/58 | F3 emits source for most tasks, but semantics fail |
| StarCoder2-3B Base | 0/58 | 1/58 | 35/58 | 47/58 | F3 emits source; five prompt-copy markers |
| SmolLM3-3B Base | 0/58 | 0/58 | 55/58 | 0/58 | F3 is 58/58 empty/EOS completions |
| Granite-3.3-2B Base | 0/58 | 0/58 | 42/58 | 55/58 | F3 emits complete-looking source |
| Qwen3-4B Base | 0/58 | 4/58 | 48/58 | 41/58 | native chat template; source emitted for all tasks |
| MiMo-7B Base | 0/58 | 9/58 | 31/58 | 34/58 | native chat template; one F3 timeout |

The machine-readable score files are named
`<slug>_sufu_{zero,f3}_boundary_20260902_score.json`.  Every row has 58/58
candidate files and `hidden_tests_exposed=false`; the F3 manifests expose the
superseded example ID.  Qwen3-14B-Base,
Qwen3-30B-A3B-Base, and OLMo-3-1125-32B have partial additive boundary
reruns, but those long jobs were deferred.  Their old rows therefore remain
pre-boundary diagnostics; partial directories have no score JSON and must not
be reported as completed evaluations.

## Train-only few-shot replacement (2026-09-02)

The leakage-safe replacement is generated by
`scripts/build_sufu_train_only_fewshot_20260902.py` and contains 229 rows with
`original_split=train` only.  The three fixed examples are
`incre-tests-synduce-constraints-sortedlist-parallel_max2`,
`incre-tests-synduce-zipper-list_sum`, and
`incre-tests-synduce-constraints-all_positive-sndmax`; all three pass the SuFu parser/type checker
and have no tests or interpreter outputs.  The runner rejects explicit
test/valid/debug rows even if a caller supplies a mixed source file.  New
scores use the `*_trainonly_valid_stopmain_20260902_score.json` suffix and supersede
the F3 values in the preceding diagnostic table.

| model | zero-shot pass@1 | train-only F3 pass@1 | zero compile errors | train-only F3 compile errors | timeouts | interface observation |
|---|---:|---:|---:|---:|---:|---|
| CodeGemma-2B PT | 0/58 | 0/58 | 58/58 | 58/58 | 0 | file-separator token in every F3 output |
| Gemma-2-2B Base | 0/58 | 0/58 | 27/58 | 56/58 | 0 | complete-looking source, mostly type/semantic failures |
| StarCoder2-3B Base | 0/58 | 1/58 | 35/58 | 48/58 | 0 | source emitted; one solved task |
| SmolLM3-3B Base | 0/58 | 0/58 | 55/58 | 0/58 | 0 | 58/58 empty/EOS F3 completions |
| Granite-3.3-2B Base | 0/58 | 0/58 | 42/58 | 55/58 | 0 | complete-looking source, mostly type/semantic failures |
| Qwen3-4B Base | 0/58 | 0/58 | 48/58 | 43/58 | 1 | native chat template; source emitted |
| MiMo-7B Base | 0/58 | 1/58 | 31/58 | 35/58 | 1 | native chat template; source emitted |

Every row has 58/58 candidate files, `hidden_tests_exposed=false`, the same
three example IDs and train-only fingerprint, and one greedy candidate per
task.  The explicit `main` stop boundary prevents long prompt-copy tails from
being treated as the model's completed program.  The full machine-readable
audit is `scripts/audit_sufu_boundary_20260902.py`.
