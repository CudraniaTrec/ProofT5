# SuFu three-shot prompt audit (2026-09-02)

This is an additive audit of the current paper-facing SuFu F3 condition.  It
does not replace the frozen score files or the master comparison table.

## What is correct

The current source is leakage-safe at the data boundary.  The three fixed
rows are in the original training split, have no `tests` or interpreter
`output` fields, and pass the SuFu parser/type checker:

* `incre-tests-synduce-constraints-sortedlist-parallel_max2`
* `incre-tests-synduce-zipper-list_sum`
* `incre-tests-synduce-constraints-all_positive-sndmax`

The target prompt contains the benchmark's natural-language description and
public type/helper prefix, but no target test inputs or expected outputs.  The
runner appends `COMPLETE SUFU SOURCE:` and stops after a generated `main`
terminator; the prompt-cleaning tests pass.

## What is not representative

The examples are valid SuFu programs, but the set is not distribution-balanced:
all three are Synduce tasks, two are nested `CList` constraint programs, one
uses a `Zipper` (there are no Zipper tasks in the 58-row test split), and none
uses `single_pass` (10/58 test tasks do).  The test split contains 33 Synduce,
20 Autolifter, and 5 Fusion tasks; it also contains 19 tree-related and 7
`CList` tasks.

Relative to the 58 test prompts, the selected demonstration prompt lengths are
1,142--1,321 characters (test median 859; about the 62nd--74th percentiles),
and source lengths are 1,272--1,502 characters (test median 1,151; about the
64th--83rd percentiles).  Every selected example has two inductive
declarations (about the 90th percentile for the test split), and two have
five or more recursive matches.  Thus they are valid and benchmark-like in
syntax, but skewed toward the harder, recursive end and omit an important
interface family.

The current high-information instruction also names the demonstrated
`Compress`, `align/label/unlabel`, and recursive data-structure patterns.  It
is intended as guidance, but it can over-bias a base model toward copying a
`CList`/constraint solution when the target is a plain list, tree, or
`single_pass` task.  This is a prompt-coverage issue, not test leakage.

The seven 58-task rows reported below were generated before the
demonstration-delimiter patch described next; their frozen provenance and
scores are unchanged.  They must not be called results of the patched prompt
until those conditions are rerun.

As an interface follow-up, the implementation now labels demonstration
sources `EXAMPLE SUFU SOURCE:` while reserving `COMPLETE SUFU SOURCE:` for the
target.  The change is covered by a unit test, but a one-task SmolLM3
regression still emitted EOS, so this delimiter change alone is not treated as
a fix and no frozen 58-task row has been replaced.  In an in-memory probe,
renaming the *target* delimiter to the demonstration-like `SOURCE EXAMPLE:`
made that one model emit text; this is a model-specific prompt hack and is not
adopted for the paper protocol without a controlled re-evaluation.

## A second confound: scoring contract

The authoritative historical SuFu score uses exact `full_stdout`.  That
output includes declaration/type-printing lines in addition to the public test
results.  A decoder-only model can therefore produce a behaviorally correct
program while differing in helper declarations, omitting an unnecessary
`target`, or choosing a different but equivalent source; exact stdout marks
that candidate as failed.

As a diagnostic only, the same frozen F3 files were rescored with
`--compare_test_results_only` (no generation or data changes):

| model | full stdout | test results only |
|---|---:|---:|
| CodeGemma-2B | 0/58 | 0/58 |
| Gemma-2-2B | 0/58 | 2/58 |
| StarCoder2-3B | 1/58 | 9/58 |
| SmolLM3-3B | 0/58 | 0/58 (all F3 outputs empty) |
| Granite-3.3-2B | 0/58 | 0/58 |
| Qwen3-4B | 0/58 | 10/58 |
| MiMo-7B | 1/58 | 21/58 |

These result-only rows are not substituted into the master table because the
frozen ProofT5 reference must be rescored under the same contract before any
paper comparison.  They do show that the near-zero exact-stdout F3 cells are
not, by themselves, evidence that every model failed to synthesize behavior.

## Controlled prompt pilot

For a prompt-only check, a second parser/type-checked train-only set was tried
on the first ten frozen targets with MiMo-7B.  It covers one Autolifter
`single_pass`, one Synduce `CList`, and one Synduce tree program:

* `incre-tests-autolifter-single-pass-length`
* `incre-tests-synduce-list-sumhom`
* `incre-tests-synduce-tree-mits`

The additive tag is `mimo_sufu_f3_balancedpilot_20260902`.  It obtained 1/10
under exact stdout and 2/10 under test-results-only.  The first ten tasks of
the current three-example condition obtain 1/10 and 5/10 respectively.  This
small pilot therefore does not justify replacing the current set solely to
raise the score; changing examples changes the adaptation behavior and needs
a pre-registered comparison on the full 58 tasks.

## Decision

The current F3 condition is syntactically valid and leakage-safe, but it is
not a clean representative few-shot estimate.  Keep its frozen numbers as a
diagnostic, not as evidence that the guidance is optimal.  Before a paper
claim, run one additive 10-task ablation with a fixed, representative set such
as `single-pass-longest10s2`, `list-sumhom`, and
`treepaths-maxPathWeight` (all train-only and parser/type-check validated),
then decide whether to rerun all 58 tasks.  In parallel, decide whether SuFu
behavior should be reported using exact stdout or test-results-only; whichever
contract is chosen must be applied identically to ProofT5 and every baseline.
