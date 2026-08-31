# Modern decoder-only Java baseline evaluation (2026-08-26)

**Provenance note:** this artifact preserves the earlier Qwen-inclusive run.
For the paper-facing comparison, Qwen is excluded because of the data-leakage
concern; use `artifacts/major_revision_decoder_only_nonqwen_20260826/` instead.

This artifact records the test-free zero-shot and fixed three-shot evaluation
requested for RQ3.  It does not fine-tune any decoder-only model.  Few-shot
means that the first three rows of
`t5_llm/data/java_mbjp_humaneval_half_train_t5.json` are placed in the
context; no test harness, hidden test, or target answer is exposed.

## Protocol

- Dataset: the frozen `mbjp_original_test_t5gemma2_20260731/test.pkl`, 67
  tasks, ten candidates per task (670 candidates per row).
- Sampling: seed `273567 + task_index * 10 + candidate_rank`; rank 0 is
  greedy and ranks 1--9 use temperature 0.8 and top-p 0.95; maximum 1,024 new
  tokens.
- Qwen3 uses full-source generation.  StarCoder2 and SmolLM3 Base use a
  code-continuation prompt: the Java prefix is reconstructed before scoring,
  and generation stops at the first completed generated Java class or copied
  training delimiter.  This is necessary because these Base checkpoints are
  code-completion models, not chat/instruction models.
- All candidates are scored by the same hidden MBJP Java scorer.  The
  trajectory `checker_seconds` field is only a standalone `javac` diagnostic;
  no hidden-test feedback or token-level checker call is used during
  generation.

## Results

| model (HF checkpoint) | context | pass@1 | pass@10 | compile errors | avg output tokens | summed LM s | summed candidate s | LM s/output token |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Qwen3-4B-Base | zero-shot | 34/67 (50.75%) | 60/67 (89.55%) | 327/670 (48.81%) | 372.1 | 5,593.1 | 5,806.2 | 0.02243 |
| Qwen3-4B-Base | 3-shot | 47/67 (70.15%) | 61/67 (91.04%) | 217/670 (32.39%) | 340.5 | 5,185.3 | 5,407.6 | 0.02273 |
| StarCoder2-3B-Base | zero-shot | 14/67 (20.90%) | 39/67 (58.21%) | 59/670 (8.81%) | 101.0 | 907.6 | 1,134.8 | 0.01342 |
| StarCoder2-3B-Base | 3-shot | 40/67 (59.70%) | 57/67 (85.07%) | 48/670 (7.16%) | 232.2 | 2,292.6 | 2,522.8 | 0.01474 |
| SmolLM3-3B-Base | zero-shot | 21/67 (31.34%) | 48/67 (71.64%) | 176/670 (26.27%) | 158.2 | 1,819.0 | 2,037.6 | 0.01716 |
| SmolLM3-3B-Base | 3-shot | 28/67 (41.79%) | 54/67 (80.60%) | 37/670 (5.52%) | 67.0 | 795.2 | 1,024.3 | 0.01771 |

The weakest zero-shot row is StarCoder2-3B Base (14/67 pass@1 and 39/67
pass@10).  SmolLM3-3B Base is the newer compact open-weight lower-bound
candidate (21/67 and 48/67); Qwen3-4B Base is the strong modern reference.
The table should retain all three models rather than selecting one based on
the test score.

Model cards/releases used for provenance: [Qwen3](https://qwenlm.github.io/blog/qwen3/),
[StarCoder2-3B](https://huggingface.co/bigcode/starcoder2-3b), and
[SmolLM3-3B-Base](https://huggingface.co/HuggingFaceTB/SmolLM3-3B-Base).

## Authoritative files

Score JSONs are in `artifacts/major_revision_decoder_only_20260826/scores/`:

- `qwen3_zero.json`, `qwen3_3shot.json`
- `starcoder2_zero.json`, `starcoder2_3shot.json`
- `smollm3_zero.json`, `smollm3_3shot.json`

Trajectory summaries with token/time accounting are the corresponding
`*_trajectory.json` files.  Complete merged candidate trees are under
`Utils/output/mbjp_original_test_t5gemma2_20260731_test_ans/` with tags
`decoder_qwen3_4b_base_zero_20260826`,
`decoder_qwen3_4b_base_3shot_20260826`,
`decoder_starcoder2_3b_base_zero_balanced_20260826`,
`decoder_starcoder2_3b_base_3shot_balanced_20260826`,
`decoder_smollm3_3b_base_zero_20260826`, and
`decoder_smollm3_3b_base_3shot_20260826`.

The runner is `baselines/java_baselines/run_decoder_only_zero_few_shot.py`;
the Base-model stopping and client changes are in
`baselines/java_baselines/model_clients.py`.
