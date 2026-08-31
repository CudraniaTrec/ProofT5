# Decoder-only few-shot follow-up (2026-08-28)

This artifact measures whether the missing few-shot condition changes the
decoder-only control results.  It is separate from the frozen zero-shot model
selection artifact from 2026-08-27 and does not overwrite any checkpoint or
paper-facing result.

The larger-model follow-up plan and current download status are recorded in
`LARGE_DECODER_ONLY_EXPERIMENT_PLAN_20260828.md`.  Its four requested
Qwen3/OLMo checkpoints are kept separate from the completed smaller-model
matrix until every weight shard has been verified.

## Leakage-controlled protocol

* All runs use three fixed training examples (`few_shot_k=3`) and one greedy
  candidate per test task.  Few-shot is prompt conditioning only; no parameter
  updates are performed.
* HumanEval-Java v15 uses 16 test tasks and GFG-v13 uses 103.  Their examples
  come from disjoint train sources (706 and 414 rows respectively), with
  JavaDoc I/O examples and test fields removed.
* SuFu uses the frozen 58-task test split and 281 synthetic training examples;
  `tests`, `output`, and `postfix` fields are removed from the examples.  No
  hidden tests, interpreter outputs, or target test rows are serialized into a
  model message.

The sanitized few-shot files are:

* `inputs/java_few_shot_train_noio_notest.json` (SHA-256
  `9d8dcf25e520a5c66557a06d74b7afdd495183e7ad17f1a37700439488978b1a`)
* `inputs/gfg_few_shot_train_noio.json` (SHA-256
  `c48a10a14ae0342024d932329c70dcfb8c55ef1ec3e150b8012a98087478d8da`)
* `inputs/sufu_few_shot_train_noio_notest.json` (SHA-256
  `20b98c17fc67bb8428f4bcfd41b62dc4d66721e2cf828ca0780ca997554f2845`)

The SuFu-native low-information control uses the separate fixed prompt set
`inputs/sufu_synthetic_realistic_three.json` (three complete parser/type-check
validated programs using the real SuFu `Compress`/`single_pass` idioms; no
tests or interpreter outputs), documented in
`SUFU_SYNTHETIC_REALISTIC_THREESHOT_SPEC.md`.  It is not sampled from the
58-task test split.  The earlier minimal set is retained only as a diagnostic.

For the revised paper-facing SuFu F3 pilot, use the more realistic
train-like examples selected by task ID from
`inputs/sufu_few_shot_train_noio_notest.json`; the protocol and IDs are fixed
in `SUFU_REALISTIC_TRAINLIKE_THREESHOT_SPEC.md`.  This set contains complete
programs with nested data, recursive helpers, and compressed alignment, while
still exposing no tests, outputs, or test-task rows.
The paper-facing invocation is now the high-information full-source setting;
the earlier prefix/no-chat invocation is retained only as a restricted
control.

The resulting CodeGemma and MiMo pilot/full scores are recorded separately in
`SUFU_REALISTIC_TRAINLIKE_RESULTS.md`; they are not retroactively inserted into
the frozen master table.

The current comparison table reports pass@1 only. It includes the complete
four-benchmark rows, plus an explicitly labelled auxiliary Qwen3.5-9B row
whose four benchmark conditions are now complete; missing cells mean not
evaluated. It is
`MASTER_COMPARISON_TABLE_HIGHINFO_SUFU_20260828.md`.  The original
`MASTER_COMPARISON_TABLE.md` remains unchanged as the pre-SuFu-update snapshot.

The underlying score JSONs may retain pass@10 because those runs generated ten
candidates, but pass@10 is intentionally not displayed in the current table.
The four larger download candidates (Qwen3-14B, Qwen3-30B-A3B, Qwen3-32B and
OLMo-3-1125-32B) remain pending because their weight snapshots are incomplete; see
`LARGE_DECODER_ONLY_EXPERIMENT_PLAN_20260828.md` and the table's status section.
Two newer complete local checkpoints are handled separately: the Qwen3.5-27B
four-benchmark matrix is running, and Qwen3.5-35B-A3B is queued. Neither is
entered as a score row until every zero/F3 condition has a complete candidate
set and an independently saved scorer JSON.

## MiMo-7B Base results

| benchmark / prompt protocol | zero-shot pass@1 | 3-shot pass@1 | zero-shot compile errors | 3-shot compile errors |
|---|---:|---:|---:|---:|
| HumanEval-Java v15 / full-source | 3/16 | **12/16** | 9/16 | **0/16** |
| GFG-v13 / full-source | 38/103 | **42/103** | 8/103 | 4/103 |
| SuFu / source-prefix | 0/58 | 0/58 | 20/58 | 28/58 |
| SuFu / full-source | 0/58 | **9/58** | 37/58 | 32/58 |

The SuFu full-source zero-shot row is an additional same-protocol control.  A
10-task smoke run was used only to detect transcript contamination and is not
used as a benchmark result.  After that check, the full 58-task runs use the
same corrected runner, which cuts `user`/`assistant` transcript markers only
after a generated program terminator.

For context, the existing MBJP no-I/O ten-candidate results also have a small
few-shot effect: CodeGemma 29/67 → 33/67 pass@1, Gemma-2 23/67 → 30/67,
StarCoder2 21/67 → 28/67, and SmolLM3 28/67 → 31/67.  Those values remain in
the frozen 2026-08-27 artifact and are not recomputed here.

## Interpretation

Few-shot is beneficial for MiMo on the two Java benchmarks, with the largest
gain on HumanEval-Java (+9 tasks).  On SuFu, examples help only when the model
is asked to emit a complete source program (9/58); simply appending examples
to the source-prefix continuation remains 0/58 and increases malformed
outputs.  Thus the SuFu result is protocol-sensitive rather than evidence
that few-shot universally solves the language-format mismatch.

Generation uses `baselines/java_baselines/run_decoder_only_zero_few_shot.py`
and `run_decoder_only_sufu.py`; scores are in the `*_score.json` files in this
directory.  Candidate manifests and trajectories record `few_shot_k=3` and
`hidden_tests_exposed=false`.

## Minimal-information HumanEval/MBJP control (2026-08-28)

The original three-shot condition above is retained as a separate, ordinary
few-shot experiment. For the requested low-information control, the runner
now supports `--few_shot_style minimal_format`. With `few_shot_k=1`, the
message contains one fixed, synthetic Java skeleton only:

```
class Example1 {
    public static void method() {
    }
}
```

The skeleton has no benchmark task text, class or method name, parameters,
solution, tests, I/O examples, or target-row content. It is generated inside
the runner and does not read a training file. The target task is still shown
in the normal way, because removing the target specification would no longer
be a code-generation evaluation. All runs below use one greedy candidate per
task; no checkpoint or frozen result was overwritten.

| model | HumanEval-Java minimal 1-shot | MBJP minimal 1-shot |
|---|---:|---:|
| CodeGemma-2B PT | 5/16 | 28/67 |
| Gemma-2-2B Base | 3/16 | 21/67 |
| StarCoder2-3B Base | 4/16 | 22/67 |
| SmolLM3-3B Base | 6/16 | 25/67 |
| Granite-3.3-2B Base | 7/16 | 27/67 |
| MiMo-7B Base | 9/16 | 30/67 |
| Qwen3-4B Base | 8/16 | 15/67 |

For the corresponding zero-shot references in the 2026-08-27 artifact, the
HumanEval values are 5/16, 3/16, 5/16, 6/16, and 6/16 for the first five
models, and MiMo is 3/16 under its valid3 run. The MBJP zero-shot references
are 29/67, 23/67, 21/67, 28/67, and 24/67 for the first five models, and MiMo
is 34/67; Qwen3's prior full-source reference is 34/67. Thus the one-skeleton
condition changes pass@1 by −1 to +3 tasks for the first five models and +6
tasks for MiMo. Qwen3 is −19 tasks on MBJP under the present full-source chat
control. The latter two effects are genuine protocol sensitivity,
not evidence of test leakage; they should be reported rather than selectively
omitted. Qwen3 HumanEval is 8/16 (no change from its zero-shot reference).

The minimal-condition score files are named `*_minimal1_score.json` in this
directory. The implementation is in
`baselines/java_baselines/run_decoder_only_zero_few_shot.py`, and regression
tests cover the guarantee that minimal examples contain no task semantics.
Every new trajectory records `hidden_tests_exposed=false`; the interrupted
MiMo three-shot MBJP attempt is diagnostic only and has no score file.

## Corrected complete-task three-shot (2026-08-28)

The requested three-shot protocol is `--few_shot_style synthetic_minimal
--few_shot_k 3`. Unlike the earlier format-only diagnostic, each demonstration
is a complete Java task and complete source answer. The prompt uses the same
imports, JavaDoc, class declaration, method signature, and open-brace shape as
the benchmark, while the three tasks are fixed generic examples (identity,
increment, and empty-string check) unrelated to every benchmark split. The
final runs preserve Java indentation and use the matched completion contract
for each model family:

| model | MBJP | HumanEval-Java | GFG-v13 |
|---|---:|---:|---:|
| CodeGemma-2B PT | **30/67** | **7/16** | **44/103** |
| Gemma-2-2B Base | **27/67** | **6/16** | **34/103** |
| StarCoder2-3B Base | **29/67** | **5/16** | **38/103** |
| SmolLM3-3B Base | **33/67** | **8/16** | **37/103** |
| Granite-3.3-2B Base | **25/67** | **6/16** | **28/103** |
| Qwen3-4B Base | **33/67** | **9/16** | **45/103** |
| MiMo-7B Base | **33/67** | **10/16** | **43/103** |

All rows above come from the final `decoder_*_syn3c_*` runs; the earlier
`syn3`/`syn3b` pilots are retained only to show why the protocol was corrected,
and the dataset-derived MiMo 3-shot score files are not used for these Java F3
values.

Each is a one-candidate greedy result, so pass@10 is not defined. The single
consolidated comparison, including all zero-shot rows and frozen ProofT5 rows, is in
`MASTER_COMPARISON_TABLE.md`.
