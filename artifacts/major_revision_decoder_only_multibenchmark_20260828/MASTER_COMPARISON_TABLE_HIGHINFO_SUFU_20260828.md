# Master four-benchmark comparison — pass@1 only (2026-08-28)

All entries are `solved/total` and report **pass@1 only**. `F3` means
three-shot prompting with three fixed training-split examples; for Java it is
the existing low-information synthetic condition, while for SuFu it is the
capability-oriented high-information full-source condition
(`guidance_profile=high_information`). The decoder-only rows use one greedy
candidate. The ProofT5 row is a frozen trained-model comparison: only its
rank-one result is shown here, not its pass@10 result.

An em dash means that the condition was not run, not that it scored zero.
Qwen3.5-9B is included as an explicitly labelled auxiliary row because it is
a larger local checkpoint evaluated under the same inference-only protocol;
its four benchmark cells below are complete.

| model | MBJP zero (p@1) | MBJP F3 (p@1) | HumanEval-Java zero (p@1) | HumanEval-Java F3 (p@1) | GFG zero (p@1) | GFG F3 (p@1) | SuFu zero (p@1) | SuFu F3 (p@1, high-information) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| CodeGemma-2B PT | 29/67 | 30/67 | 5/16 | 7/16 | 40/103 | 44/103 | 0/58 | 0/58 |
| Gemma-2-2B Base | 23/67 | 27/67 | 3/16 | 6/16 | 27/103 | 34/103 | 0/58 | 0/58 |
| StarCoder2-3B Base | 21/67 | 29/67 | 5/16 | 5/16 | 39/103 | 38/103 | 0/58 | 1/58 |
| SmolLM3-3B Base | 28/67 | 33/67 | 6/16 | 8/16 | 33/103 | 37/103 | 0/58† | 0/58† |
| Granite-3.3-2B Base | 24/67 | 25/67 | 6/16 | 6/16 | 26/103 | 28/103 | 0/58 | 0/58 |
| Qwen3-4B Base | 34/67 | 33/67 | 8/16 | 9/16 | 25/103 | 45/103 | 0/58 | 5/58 |
| MiMo-7B Base | 34/67† | 33/67 | 3/16 | 10/16 | 38/103 | 43/103 | 0/58 | 8/58 |
| Qwen3.5-9B Base (auxiliary) | 16/67 | 11/67 | 7/16 | 8/16 | 28/103 | 26/103 | 0/58 | 0/58 |
| **ProofT5 (ours, frozen trained model)** | **17/67** | N/A | **8/16** | N/A | **31/103** | N/A | **25/58** | N/A |

The SuFu zero/F3 cells for decoder-only models are from the complete 58-task
native parser/executor evaluations in the files named
`decoder_*_sufu_highinfo_{zero,f3}_fullsource_20260828_score.json`, except
MiMo F3, whose file is
`decoder_mimo_sufu_highinfo_trainlike3_fullsource_score.json`.  Every row has
58/58 generated candidates and no hidden tests or interpreter outputs were
sent to the model.  The full audit, including compilation-error rates, is in
`SUFU_REALISTIC_TRAINLIKE_RESULTS.md`.

SmolLM3 emitted an empty completion under this SuFu full-source protocol; its
0/58 cells are therefore a recorded interface failure, not evidence of 58
valid compilations. It should be described as such in the manuscript. The
`†` marker on SmolLM3's SuFu cells identifies this interface failure; the
`†` marker on MiMo's MBJP zero-shot cell identifies its single-candidate pilot
status.

The Java columns are copied from the audited decoder-only runs and are
unchanged by the SuFu rerun. Java F3 remains intentionally low-information;
SuFu F3 intentionally does not use that restriction. The underlying score
JSONs still retain pass@10 where it was generated, but pass@10 is deliberately
omitted from this comparison table.

## Larger models investigated but not yet reportable

| model | local status | why it is not a result row |
|---|---|---|
| Qwen3-14B-Base | incomplete snapshot | only metadata and `.incomplete` weight-cache files; no verified weight set or score |
| Qwen3-30B-A3B-Base | incomplete snapshot | only metadata and `.incomplete` weight-cache files; no verified weight set or score |
| Qwen3-32B | incomplete snapshot | only metadata and `.incomplete` weight-cache files; no verified weight set or score |
| OLMo-3-1125-32B | incomplete snapshot | only metadata and `.incomplete` weight-cache files; no verified weight set or score |
| Qwen3.5-27B | full local checkpoint; matrix running | full four-benchmark zero/F3 generation is running under the same protocol; no score is inserted until all 8 conditions pass completeness checks |
| Qwen3.5-35B-A3B | full local checkpoint; queued | 35B/3B-active MoE follow-up is queued after the 27B run to avoid simultaneous memory pressure |

These four candidates remain in `LARGE_DECODER_ONLY_EXPERIMENT_PLAN_20260828.md`
as pending downloads. They will be added only after all shards pass the
snapshot check, a one-row generation smoke test succeeds, and the same
benchmark protocol is completed. Qwen3.5-9B had a complete local checkpoint,
so its full four-benchmark follow-up is reported above. Its eight score files are
`qwen35_9b_mbjp_zero_score.json`, `qwen35_9b_mbjp_syn3_score.json`,
`qwen35_9b_he_zero_full_score.json`, `qwen35_9b_he_f3_full_score.json`,
`qwen35_9b_gfg_zero_full_score.json`,
`qwen35_9b_gfg_f3_full_p1_score.json`,
`qwen35_9b_sufu_zero_highinfo_score.json`, and
`qwen35_9b_sufu_f3_highinfo_score.json` in this artifact directory.
