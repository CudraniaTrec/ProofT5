# Effect-first SynCode/Repilot reruns (2026-09-03)

This record covers the requested accuracy-first attempts.  All pilots use the
same T5Gemma2-2B paper-comparison checkpoint, the frozen MBJP prompt, the
existing full-output scorer, fixed seeds, and no hidden-test information during
generation.  Existing 67-task result trees are not overwritten.

## Repilot

| Variant | Scope | Pass@1 | Pass@10 | Compile errors |
|---|---:|---:|---:|---:|
| Frozen sound-default JDT adapter | 67 x 10 | 10/67 | 23/67 | 112/670 |
| IDE capabilities + safe ACTIVE (existing full run) | 67 x 10 | 10/67 | 23/67 | 112/670 |
| Replacement-edit unknown handling + Java safe close, top-k 200 | 10 x 10 | 2/10 | 5/10 | 17/100 |
| JDT queried on every token, same safe policy | 10 x 10 | 2/10 | 5/10 | 17/100 |
| Proactive top-ranked IDE completion + safe close | 10 x 10 | 1/10 | 3/10 | 59/100 |
| Temperature 0.2, safe JDT | 10 x 10 | 2/10 | 3/10 | 6/100 |
| Temperature 1.0, safe JDT | 10 x 10 | 2/10 | 4/10 | 21/100 |
| Project default seed 19970316, safe JDT | 10 x 10 | 2/10 | 5/10 | 17/100 |

The replacement-edit fix is now the default behavior for future runs: a JDT
item whose `target` rewrites an already-emitted `source` is treated as an
unknown answer rather than an empty completion list.  This prevents an
unsound false prune.  Java class-brace completion and decoder-start-only
`full_output` are explicit opt-in diagnostics; frozen forced-prefix outputs are
unchanged.  None of the validated pilots produced a Pass@1 increase over the
2/10 matched pilot, so no accuracy gain is claimed.

Pilot outputs and scores:

- `repilot_nonappend_safe_pilot10_20260903`
- `repilot_nonappend_safeclose_pilot10_20260903`
- `repilot_everytoken_safeclose_pilot10_20260903`
- `repilot_proactive_top_fix_pilot10_20260903`
- `repilot_temp02_safeclose_pilot10_20260903`
- `repilot_temp10_safeclose_pilot10_20260903`
- `repilot_seed19970316_safe_pilot10_20260903`

The interrupted decoder-start-only control is retained as a diagnostic partial
tree; its completed tasks 0--1 are 0/2 Pass@1 and 0/2 Pass@10.  It is not a
paper result.

## SynCode

| Variant | Scope | Pass@1 | Pass@10 | Compile errors |
|---|---:|---:|---:|---:|
| Frozen proposal-preserving Java CFG | 67 x 10 | 10/67 | 23/67 | 122/670 |
| Strict grammar-mask + proposal-preserving rejection | 10 x 10 | 0/10 | 0/10 | 22/30 |
| Grammar-mask, top-k 200 | 10 x 10 | 2/10 | 5/10 | 19/100 |
| Grammar-mask + full-vocabulary fallback after top-k exhaustion | 10 x 10 | 2/10 | 5/10 | 18/100 |

The full-vocabulary fallback is effect-first and opt-in (`--expand_sampling_support`):
when every top-k proposal is rejected, the decoder retries against the full
vocabulary before stopping.  It reduced pilot compile errors by one, but did
not recover a functionally correct task.  Strict grammar mode was substantially
worse because malformed prefixes trigger SynCode's parser fallback and the
CFG cannot repair semantic mistakes.

Pilot outputs and scores:

- `syncode_accuracy_strict_pilot10_20260903`
- `syncode_topk200_pilot10_20260903`
- `syncode_expandfull_pilot10_20260903`

## Interpretation

The requested “cost can be high” policy has been honored: the every-token JDT
pilot and full-vocabulary SynCode fallback were run without a time-saving
shortcut.  The evidence shows that checker cost is not the limiting factor on
this checkpoint: the dominant failures are semantically incorrect but
syntactically/IDE-feasible model programs.  Spending more checker time cannot
guarantee a higher Pass@1, and selecting a seed, candidate, or hidden-test
outcome after looking at the test set would be invalid.  The full frozen rows
therefore remain the headline RQ3 comparison; these effect-first variants are
reported as diagnostics unless a predeclared full run is requested.

The adapter still keeps the two baselines independent.  Repilot uses only the
modified Eclipse JDT `newCompletion` protocol described by the [Repilot
paper](https://arxiv.org/html/2309.00608) and [official
repository](https://github.com/ise-uiuc/Repilot); no SynCode grammar mask is
imported into it.
