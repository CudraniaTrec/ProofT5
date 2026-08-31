# Non-Qwen decoder-only baselines and iterative feedback (2026-08-26)

This supplement is the paper-facing decoder-only comparison requested after
excluding Qwen-family checkpoints because of possible training-data leakage.
All rows use the frozen MBJP test set (67 tasks, 10 candidates per task) and
the unchanged hidden Java scorer.  Existing Qwen rows remain archived in the
older decoder-only artifact but are not part of this table.

## Protocol

- Zero-shot has no demonstrations.  Three-shot places the first three clean
  training examples in the prompt; it is inference-only and does not update
  model parameters.
- Rank 0 is greedy; ranks 1--9 use temperature 0.8 and top-p 0.95.  The
  maximum is 1,024 new tokens, with the frozen seed schedule
  `273567 + task_index * 10 + candidate_rank`.
- StarCoder2, SmolLM3, and Granite Base checkpoints are code-completion
  models.  The benchmark Java prefix is passed unchanged and the generated
  continuation is materialized back onto that prefix.  This is generic source
  reconstruction, not syntax/type/Coq guidance or model-specific tuning.
- Iterative rows start from the same zero-shot prompt and allow at most two
  repair calls, triggered only by standalone `javac` diagnostics.  No hidden
  tests, test harnesses, semantic feedback, or token-level checker calls are
  exposed during generation.  Round-0 controls are scored from each
  trajectory's initial source.

## Results

| model | ordinary context | pass@1 | pass@10 | compile errors |
|---|---|---:|---:|---:|
| StarCoder2-3B-Base | zero-shot | 37/67 (55.22%) | 56/67 (83.58%) | 62/670 |
| StarCoder2-3B-Base | 3-shot | 40/67 (59.70%) | 57/67 (85.07%) | 48/670 |
| SmolLM3-3B-Base | zero-shot | 36/67 (53.73%) | 53/67 (79.10%) | 60/670 |
| SmolLM3-3B-Base | 3-shot | 42/67 (62.69%) | 56/67 (83.58%) | 128/670 |
| Granite-3.3-2B-Base | zero-shot | 28/67 (41.79%) | 48/67 (71.64%) | 128/670 |
| Granite-3.3-2B-Base | 3-shot | 35/67 (52.24%) | 48/67 (71.64%) | 52/670 |
| Gemma-2-2B-Base | zero-shot | 27/67 (40.30%) | 46/67 (68.66%) | 88/670 |
| Gemma-2-2B-Base | 3-shot | 33/67 (49.25%) | 44/67 (65.67%) | 45/670 |
| StarCoder2-3B-Base | iterative final | 33/67 (49.25%) | 54/67 (80.60%) | 77/670 |
| StarCoder2-3B-Base | iterative round-0 | 33/67 (49.25%) | 53/67 (79.10%) | 82/670 |
| SmolLM3-3B-Base | iterative final | 36/67 (53.73%) | 54/67 (80.60%) | 61/670 |
| SmolLM3-3B-Base | iterative round-0 | 36/67 (53.73%) | 54/67 (80.60%) | 52/670 |
| Granite-3.3-2B-Base | iterative final | 30/67 (44.78%) | 46/67 (68.66%) | 126/670 |
| Granite-3.3-2B-Base | iterative round-0 | 29/67 (43.28%) | 45/67 (67.16%) | 148/670 |
| Gemma-2-2B-Base | iterative final | 27/67 (40.30%) | 45/67 (67.16%) | 77/670 |
| Gemma-2-2B-Base | iterative round-0 | 27/67 (40.30%) | 45/67 (67.16%) | 73/670 |
| ProofT5 (frozen paper reference) | trained model | 17/67 (25.37%) | 29/67 (43.28%) | 3/670 |

The clean, protocol-aligned ordinary runs do not justify selecting a baseline
after inspecting scores: StarCoder2 obtains 37/67 pass@1 and 56/67 pass@10 in
zero-shot, while SmolLM3 obtains 36/67 and 53/67.  The older StarCoder2 and
SmolLM3 ordinary rows are retained only as superseded diagnostics because
their zero-shot prompt-token counts did not match the iterative contract.
Granite is the closest size-matched recent open Base model: its model card
identifies it as decoder-only, 2.5B parameters, released 2025-04-16, and
Apache-2.0.  SmolLM3-3B-Base was released in July 2025; StarCoder2-3B was
released in February 2024.  Keep all four rows to avoid selecting a baseline
after looking at test scores.

The ordinary generation cost (sums over 670 candidates and parallel workers)
was:

| model/context | input tokens | output tokens | LM seconds | javac seconds |
|---|---:|---:|---:|---:|
| StarCoder2 zero-shot | 107,600 | 119,689 | 1,624.8 | 243.6 |
| StarCoder2 3-shot | 1,125,330 | 155,565 | 2,969.6 | 234.3 |
| SmolLM3 zero-shot | 98,460 | 104,820 | 2,388.9 | 243.6 |
| SmolLM3 3-shot | 1,017,030 | 125,168 | 2,765.6 | 226.0 |
| Granite zero-shot | 107,600 | 148,998 | 3,128.7 | 245.6 |
| Granite 3-shot | 1,125,330 | 168,952 | 3,498.0 | 233.2 |
| Gemma-2-2B zero-shot | 113,930 | 151,257 | 2,812.5 | 240.3 |
| Gemma-2-2B 3-shot | 1,188,610 | 181,574 | 3,350.7 | 232.8 |

## Iterative cost

Across 670 candidates, the iterative trajectories used:

| model | model calls (repairs) | input tokens | output tokens | LM seconds | javac seconds | summed candidate seconds |
|---|---:|---:|---:|---:|---:|---:|
| StarCoder2-3B-Base | 854 (184) | 292,507 | 269,477 | 3,769.8 | 299.7 | 4,069.5 |
| SmolLM3-3B-Base | 796 (126) | 212,909 | 131,218 | 2,293.2 | 272.7 | 2,565.9 |
| Granite-3.3-2B-Base | 1,030 (360) | 484,616 | 387,368 | 8,220.9 | 361.3 | 8,582.2 |
| Gemma-2-2B-Base | 837 (167) | 281,903 | 196,818 | 3,628.7 | 282.5 | 3,911.1 |

The corresponding trajectory JSONs contain per-round timings.  These elapsed
times are sums over parallel workers, not wall-clock times; the extra calls
are caused only by failed standalone `javac` compilation.

For Gemma2, LM time per generated token is 0.01859 s (zero-shot), 0.01845 s
(3-shot), and 0.01844 s (iterative).  Relative to the 670-candidate zero-shot
control, iterative feedback adds 167 model calls, 45,561 output tokens, 816.2
LM seconds, and 42.1 `javac` seconds (858.3 summed candidate seconds).

The feedback effect is small: StarCoder2 changes from 33/53 to 33/54,
SmolLM3 remains 36/54, Granite changes from 29/45 to 30/46, and Gemma2
remains 27/45 (pass@1/pass@10).  Gemma2's round-0 and final pass@1 are both
27/67 and its pass@10 is 45/67; the 167 repair calls do not add a solved task
and increase the aggregate compile-error count from 73/670 to 77/670.  The ordinary three-shot rows are often stronger than their
iterative zero-shot counterparts, and every ordinary decoder-only row exceeds
the frozen ProofT5 reference (17/29).  The revision should therefore present
these as an honest architecture/control comparison, not as evidence that
ProofT5 is uniformly better than modern decoder-only models.

## Gemma2 status

After the authorized Hugging Face token became available, the official
`google/gemma-2-2b` Base checkpoint was downloaded locally to
`Utils/models/Gemma-2-2B/` and evaluated without fine-tuning.  The repository is
gated and the access approval/token state is therefore part of the provenance;
the model card is [Gemma-2-2B](https://huggingface.co/google/gemma-2-2b).
The instruction-tuned variant was not used.

Gemma2 is a decoder-only Base model.  Its code-completion continuation is
materialized onto the unchanged Java prefix using the same generic protocol as
the other Base models.  A preliminary full-source smoke prompt generated only
a method-body continuation and is not part of the official score; the reported
rows use the protocol-aligned `prefix_completion` mode.  No syntax, type, Coq,
or model-specific tuning was applied.

## Authoritative files

- Ordinary scores: `artifacts/major_revision_decoder_only_20260826/scores/{starcoder2_zero_clean,starcoder2_3shot_clean,smollm3_zero_clean,smollm3_3shot_clean}.json` (Granite direct rows are `granite33_zero.json` and `granite33_3shot.json`; Gemma2 rows are `gemma2_zero.json` and `gemma2_3shot.json`).
- Gemma2 iterative scores: `artifacts/major_revision_decoder_only_20260826/scores/{gemma2_iterative_round0,gemma2_iterative}.json`.
- Ordinary trajectories: the corresponding merged trees under `Utils/output/mbjp_original_test_t5gemma2_20260731_test_ans/decoder_{starcoder2_3b,smollm3_3b}_base_{zero,3shot}_clean_merged_20260826/`.
- Iterative merged candidate trees: `Utils/output/mbjp_original_test_t5gemma2_20260731_test_ans/decoder_{starcoder2_3b,smollm3_3b,granite33_2b,gemma2_2b}_iterative_merged_20260826/` (the Gemma2 round-0 control is `decoder_gemma2_2b_iterative_round0_merged_20260826/`).
- Runner: `baselines/java_baselines/run_iterative_refinement.py`
- Generic Base-model materialization: `baselines/java_baselines/run_decoder_only_zero_few_shot.py`
- Model provenance: [StarCoder2-3B](https://huggingface.co/bigcode/starcoder2-3b), [SmolLM3-3B-Base](https://huggingface.co/HuggingFaceTB/SmolLM3-3B-Base), [Granite-3.3-2B-Base](https://huggingface.co/ibm-granite/granite-3.3-2b-base), [Gemma-2-2B](https://huggingface.co/google/gemma-2-2b).
