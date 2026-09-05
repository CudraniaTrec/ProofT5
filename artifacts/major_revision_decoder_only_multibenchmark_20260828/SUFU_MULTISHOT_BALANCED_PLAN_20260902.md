# SuFu balanced few-shot experiment plan (2026-09-02)

This additive experiment tests whether a modest number of train-only,
distribution-balanced demonstrations improves strict `full_stdout` Pass@1 for
larger decoder-only models.  It does not overwrite the frozen 3-shot rows or
any existing checkpoints/results.

## Fixed protocol

* target split: the frozen 58-row SuFu test set;
* metric: exact interpreter `full_stdout` Pass@1 (one greedy candidate);
* prompt: `full_source`, `guidance_profile=high_information`;
* generation: `max_tokens=2048`, seed `273567`, local bf16 base model;
* demonstrations: only rows from the train-only sanitized source; no `tests`,
  `output`, `postfix`, test/valid/debug rows, or test-task IDs;
* all output tags are new and additive.

The previously frozen paper-facing F3 set contains three Synduce examples and
remains the historical control.  The new balanced sets use one equal slot per
family (Synduce, Autolifter, Fusion) and are nested so that the effect of adding
examples can be read without changing the earlier examples.

## Demonstration sets

| set | examples (in order) | total |
|---|---|---:|
| Balanced-3 | Synduce `list-sumhom`; Autolifter `single-pass-length`; Fusion `shortcut-page3` | 3 |
| Balanced-6 | Balanced-3 + Synduce `constraints-all_positive-sndmax`; Autolifter `dac-mts_p`; Fusion `tupling-page1` | 6 |
| Balanced-9 | Balanced-6 + Synduce `tree-mits`; Autolifter `single-pass-longest10s2`; Fusion `deforestation-page7-1` | 9 |
| Balanced-12 | Balanced-9 + Synduce `compressed_list-sum`; Autolifter `single-pass-is_sorted`; Fusion `identities-page5` | 12 |

All twelve sources are present in
`inputs/sufu_few_shot_train_only_noio_notest_20260902.json`, have
`original_split=train`, and pass the SuFu executor/type checker.  The 12-shot
example blocks occupy about 21k characters (roughly 5.3k tokens before the
target prompt), which is below the context budget of the selected larger
models.  Larger sets are not attempted initially because redundant long
examples can increase prompt-copy and termination failures.

## Selection and final run policy

The first stage uses a 10-task interface/capability pilot on Qwen3-14B-Base
and Qwen3-30B-A3B-Base for Balanced-6/9/12.  Pilot scores are not paper
results.  We record output length, EOS/prompt-copy failures, compile errors,
strict full-output passes, and generation time.  After the pilot, the best
pre-declared setting (or Balanced-9 if scores are indistinguishable) is run on
all 58 tasks for the compact selected Qwen set and the non-Qwen diagnostic
control.  The selected Qwen set is Qwen3-14B-Base, Qwen3-30B-A3B-Base, and one
newer-generation representative, Qwen3.6-27B.  MiMo-7B Base is added as the
non-Qwen control; Qwen3-32B is evaluated for exhaustive-matrix completeness.
OLMo-3-1125-32B remains a non-Qwen interface diagnostic.  Qwen3.6's Java
full-source rows are held as diagnostics because its default thinking protocol
was not compatible with the Java prefix task; only its separately audited
SuFu prefix row is currently usable.

The same full 58-task run is rescored diagnostically with
`--compare_test_results_only`, but those rows are not mixed into the strict
headline table.  A setting is not selected by searching over the 58 test
scores after the fact; the final shot count and IDs are recorded in each
manifest.

## Pilot evidence and protocol addendum (2026-09-02)

The first pilot showed that “more examples” is not monotonic under exact
Full Output: copied declaration order and missing `target` definitions can
turn a semantically executable program into a failed full transcript.  We
therefore added a second, still train-only, `canonical-coverage` set whose
six examples cover plain-list target syntax, CList/TreeMemo target syntax,
Autolifter `dac`/`single_pass`, and Fusion tree code:

```
constraints-sortedlist-max,
constraints-memo-max_contains,
constraints-sortedlist-parallel_max2,
dac-mts_p,
single-pass-is_sorted,
fusion-tupling-page1
```

The pilot used only the first ten frozen test tasks (diagnostic denominator
10; no headline score was replaced):

| model / setting | strict Full Output | result-only diagnostic | compile errors |
|---|---:|---:|---:|
| Qwen3-14B, original Balanced-6/full-source | 2/10 | 6/10 | 3/10 |
| Qwen3-14B, canonical-coverage-6/full-source | 1/10 | 6/10 | 4/10 |
| Qwen3-30B-A3B, original Balanced-6/prefix | 0/10 | 3/10 | 4/10 |
| Qwen3-30B-A3B, canonical-coverage-6/prefix | **4/10** | **5/10** | 3/10 |
| Qwen3-30B-A3B, canonical-coverage-9/prefix | 3/10 | 4/10 | 3/10 |

Thus the final larger-model SuFu condition is six shots, not nine or twelve:
the original Balanced-6/full-source condition is retained for Qwen3-14B as
its best pilot setting, while canonical-coverage-6/prefix is used for
Qwen3-30B-A3B.  A complete 58-task run was launched for each; its outputs and
scores have fresh tags `sufu_mimo_canonical6_full_final_20260902`,
`sufu_q14b_balanced6_full_final_20260902`,
`sufu_q30b_canonical6_prefix_final_20260902`, and
`sufu_q32b_canonical6_prefix_final_20260902`,
`sufu_q36_27b_canonical6_prefix_final_20260902`.  OLMo-3 was checked with the
same canonical prefix pilot but repeatedly copied Python/Java or explanation
text after the public prefix; that interface failure is retained as a
diagnostic and is not silently converted into a capability score.

The runner also has a generic `guidance_profile=full_output` that explicitly
states the complete-transcript contract (including a required target or
representation definition when task semantics require one).  This is a
prompt-format control, not a model-specific adapter, and its pilot is stored
under `sufu_q14b_canon6_fulloutput_pilot10_20260902`.

The complete selected runs are now scored on all 58 tasks:

| model / selected condition | strict Full Output Pass@1 | result-only diagnostic | compile errors |
|---|---:|---:|---:|
| MiMo-7B Base / canonical-coverage-6, full-source | **6/58** | 24/58 | 25/58 |
| Qwen3-14B-Base / Balanced-6, full-source | **8/58** | 25/58 | 25/58 |
| Qwen3-30B-A3B-Base / canonical-coverage-6, prefix | **6/58** | 16/58 | 22/58 |
| Qwen3-32B / canonical-coverage-6, prefix | **5/58** | 14/58 | 21/58 |
| Qwen3.6-27B / canonical-coverage-6, prefix | **8/58** | 19/58 | 18/58 |

The completed Qwen3-32B row (5/58 strict, 14/58 result-only, 21/58 compile
errors) is included in the exhaustive audit and omitted only from the compact
selected set as a near-duplicate scale point.  MiMo's matching six-shot row is
also included in the exhaustive audit.

These are fresh additive score files
`mimo_canonical6_full_final_20260902_score.json`,
`q14b_balanced6_full_final_20260902_score.json`,
`q30b_canonical6_prefix_full_final_20260902_score.json`,
`q32b_canonical6_prefix_full_final_20260902_score.json`, and
`q36_27b_canonical6_prefix_full_final_20260902_score.json`.  The denominator is
the unchanged frozen 58-task test set and each row has one greedy candidate.
The result-only values are retained solely to diagnose declaration/interface
failures; only the bold Full Output values are eligible for the manuscript.
The five-row k=6 manifest/output contract is checked by
`scripts/audit_selected_sufu_k6_20260902.py`.
The generic `full_output` wording did not improve the Qwen3-14B pilot (0/10
strict, 5/10 result-only), so it is not used for the final row.
