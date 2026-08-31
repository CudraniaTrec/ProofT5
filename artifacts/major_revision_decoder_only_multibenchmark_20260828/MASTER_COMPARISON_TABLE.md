# Master four-benchmark comparison (2026-08-28)

> Pre-SuFu-update snapshot.  The complete table with the new SuFu
> high-information zero/F3 results is in
> `MASTER_COMPARISON_TABLE_HIGHINFO_SUFU_20260828.md`; this file is retained
> unchanged below for auditability.

Counts are `solved/total`; `p1/p10` means pass@1/pass@10. `—` means that a
condition has not been run, not that it scored zero. MBJP zero-shot entries
show the existing ten-candidate `p1 / p10` controls (except MiMo's marked
one-candidate pilot); the other decoder-only zero-shot entries are one-candidate
`p1` pilots. The corrected few-shot condition is synthetic three-shot (`F3`):
three complete, tiny, dataset-independent Java tasks (`identity`, `increment`,
and `isEmpty`) with their complete source answers. F3 runs use one greedy
candidate, so their p10 is unavailable.

| model | MBJP zero | MBJP F3 | HumanEval zero | HumanEval F3 | GFG zero | GFG F3 | SuFu zero | SuFu F3 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| CodeGemma-2B PT | 29/67 / 48/67 | **30/67** | 5/16 | **7/16** | 40/103 | **44/103** | 0/58 | N/A |
| Gemma-2-2B Base | 23/67 / 43/67 | **27/67** | 3/16 | **6/16** | 27/103 | **34/103** | 0/58 | N/A |
| StarCoder2-3B Base | 21/67 / 50/67 | **29/67** | 5/16 | **5/16** | 39/103 | **38/103** | 0/58 | N/A |
| SmolLM3-3B Base | 28/67 / 42/67 | **33/67** | 6/16 | **8/16** | 33/103 | **37/103** | 0/58 | N/A |
| Granite-3.3-2B Base | 24/67 / 41/67 | **25/67** | 6/16 | **6/16** | 26/103 | **28/103** | 0/58 | N/A |
| Qwen3-4B Base | 34/67 / 60/67* | **33/67** | 8/16 | **9/16** | 25/103 | **45/103** | 0/58 | N/A |
| MiMo-7B Base | 34/67† | **33/67** | 3/16 | **10/16** | 38/103 | **43/103** | 0/58 | N/A |
| **ProofT5 (ours)** | **17/67 / 29/67** | N/A | **8/16 / 9/16** | N/A | **31/103 / 48/103** | N/A | **25/58 / 29/58** | N/A |

ProofT5 is a trained encoder-decoder system, not a decoder-only prompt
baseline; therefore a Java decoder-only F3 prompt is not a valid apples-to-
apples condition for it. Its frozen ten-candidate row is shown as the method
comparison. The authoritative ProofT5 table is in
`docs/MAJOR_REVISION_FINAL_PACKAGE_20260824.md`.

All decoder-only SuFu F3 cells are N/A because the corrected F3 is a Java
condition and SuFu is not Java. For reference, the earlier SuFu-specific three-shot control
was 0/58 with source-prefix and 9/58 with full-source. A complete SuFu few-shot
matrix requires a separate SuFu-native set of three synthetic complete tasks.

The final, format-matched F3 score files follow
`decoder_<model>_syn3c_<benchmark>_score.json` and are present for every
decoder-only model in the table: CodeGemma, Gemma-2, StarCoder2, SmolLM3,
Granite, Qwen3, and MiMo (three Java benchmarks each). This makes 21 score
files; the exact names can be enumerated with:

```bash
ls artifacts/major_revision_decoder_only_multibenchmark_20260828/*syn3c*_score.json
```

The MiMo F3 rows in the table are read from these final `decoder_mimo_syn3c_*`
manifests, whose arguments explicitly record `few_shot_k=3`,
`few_shot_style=synthetic_minimal`, and the three synthetic example IDs. They
are not the earlier `pilot_mimo_he_3shot_score.json` or
`pilot_mimo_gfg_3shot_score.json` files. The only reused MiMo few-shot result
is the separately marked SuFu-specific diagnostic described above.

All 21 final Java F3 runs have complete task coverage, no missing outputs, and
no hidden test fields in their model messages. The implementation and exact
synthetic examples are in
`baselines/java_baselines/run_decoder_only_zero_few_shot.py` under
`--few_shot_style synthetic_minimal --few_shot_k 3`.
The exact three-task specification is also recorded in
`SYNTHETIC_THREESHOT_SPEC.md`.
Earlier `syn3` and `syn3b` pilots are retained only as diagnostics; the table
uses `syn3c`, which preserves Java indentation. The old dataset-derived MiMo
three-shot files and the invalid full-source CodeGemma GFG attempt are not
used.
