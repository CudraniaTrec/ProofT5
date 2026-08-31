# Decoder-only Java controls without benchmark I/O examples (2026-08-26)

This artifact contains a corrected local-inference protocol for the modern
decoder-only controls.  The target prompts and the three-shot demonstrations
remove all JavaDoc lines of the form `> input` and their expected-output line.
The frozen `test` harness is retained only for post-generation scoring and is
never serialized into model messages.

## Protocol

- Frozen MBJP test split: 67 tasks, 10 candidates per task (670 candidates).
- Prefix-completion mode for all Base/code models; no model-specific tuning.
- Rank 0 is greedy; ranks 1--9 use temperature 0.8, top-p 0.95, and seed
  `273567 + task_index * 10 + candidate_rank`.
- Maximum 1,024 new tokens; Java scoring uses the frozen executable harness
  with a 10-second per-candidate timeout.
- The scorer verifies `benchmark`, `original_split`, and `test` identity against
  the frozen pickle while allowing the prompt-only I/O sanitization.

The runner now accepts `--reject_io_examples` and fails closed if either a
target or few-shot source row still contains a JavaDoc I/O example.

## Results

All rows below use the same sanitized target input and scorer.  Values are
`pass@1 / pass@10` over 67 tasks.

| model | context | pass@1 | pass@10 | compile errors | timeouts |
|---|---|---:|---:|---:|---:|
| CodeGemma-2B PT | zero-shot | 29/67 (43.28%) | 48/67 (71.64%) | 84/670 | 1 |
| CodeGemma-2B PT | 3-shot | 33/67 (49.25%) | 45/67 (67.16%) | 49/670 | 1 |
| Gemma-2-2B Base | zero-shot | 23/67 (34.33%) | 43/67 (64.18%) | 68/670 | 2 |
| Gemma-2-2B Base | 3-shot | 30/67 (44.78%) | 41/67 (61.19%) | 47/670 | 2 |
| StarCoder2-3B Base | zero-shot | 21/67 (31.34%) | 50/67 (74.63%) | 94/670 | 0 |
| StarCoder2-3B Base | 3-shot | 28/67 (41.79%) | 47/67 (70.15%) | 65/670 | 4 |
| SmolLM3-3B Base | zero-shot | 28/67 (41.79%) | 42/67 (62.69%) | 88/670 | 1 |
| SmolLM3-3B Base | 3-shot | 31/67 (46.27%) | 47/67 (70.15%) | 131/670 | 1 |
| Granite-3.3-2B Base | zero-shot | 24/67 (35.82%) | 41/67 (61.19%) | 153/670 | 2 |

The CodeGemma zero-shot pass@1 (43.28%) is close to the model card's MBPP
pass@1 value (43.6%) and its BabelCode-Java MBPP value (41.8%).  MBJP is a
different Java benchmark, so its scores are not expected to equal HumanEval or
MBPP exactly.  The official model card is available at
https://huggingface.co/google/codegemma-2b.

## Leakage audit

- Original target rows: 400 JavaDoc I/O-example lines.
- Sanitized target rows: 0 I/O-example lines.
- Sanitized three-shot IDs: `MBJP/1`, `MBJP/2`, `MBJP/3`.
- Sanitized target IDs and frozen test harnesses are unchanged.
- A run on the original dataset with `--reject_io_examples` fails closed before
  model loading.

## Authoritative files

- Sanitized inputs: `inputs/java_mbjp_original_test_noio.json` and
  `inputs/java_mbjp_humaneval_half_train_noio.json`.
- Score JSONs: `scores/codegemma2b_noio_zero.json`,
  `scores/codegemma2b_noio_3shot.json`, `scores/gemma2_noio_zero.json`,
  `scores/gemma2_noio_3shot.json`, `scores/starcoder2_noio_zero.json`,
  `scores/smollm3_noio_zero.json`, and `scores/granite33_noio_zero.json`.
- Candidate trees are under
  `Utils/output/mbjp_original_test_t5gemma2_20260731_test_ans/` with matching
  `*_noio_*_merged_20260826` tags.
- Code and guard: `baselines/java_baselines/prepare_no_io_datasets.py` and
  `baselines/java_baselines/run_decoder_only_zero_few_shot.py`.
