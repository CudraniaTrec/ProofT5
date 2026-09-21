# SuFu 2B pair rerun and checkpoint recovery (2026-09-15)

## Why

The reported TyFlow-2B SuFu row (43.10 / 50.00 / 5.03 / 0.00) entered the
paper on 2026-06-30 (commit ce2dd2c) and had no surviving per-task arrays or
score record on disk; the artifact README's earlier attribution to
`Modelsufucoq_t5gemma2_2b_corrected_formal100pass` epoch 80 was unverifiable.
Both 2B SuFu rows (baseline and TyFlow) predate the record-keeping, so the
Appendix D 2B SuFu block carried placeholder p-values copied from the 220M
arrays (marked `TODO(placeholdder-2b-sufu)`).

This package records the 2026-09-15 rerun that resolves both sides.

## Protocol

Generation: `run.py --eval`, beam 10, `length_penalty=0.1`,
`coq_candidate_multiplier=20`, `batch_size_eval=1`, DDP bf16 (8 or 4 x H200),
per-task max decode length = task `max_code_len`. Baseline generation:
`t5_llm/finetune_t5gemma2.py --generate_only --topk 10
--generation_max_length 1024 --bf16` (protocol of the frozen 2026-07-30
baseline sweeps). Scoring: `score_sufu_no_write.py --pass_at_k 10 --workers
64 --timeout 10`, executor-comparison protocol unchanged from the frozen
220M stats. Test set: the frozen 58-problem SuFu split (byte-identical
`test.pkl` across all tasks used here, hash 5c927668b8156266).

## Frozen checkpoints

- TyFlow side: `Utils/models/Modelsufu_original_synthetic_half_train_t5gemma2_20260731_complete281_formal100_8gpu_b5_lr5em5_20260731_105207/last_model.ckpt`
  SHA256 322b88453c7bcb4ee820071e8f50b838aeaab0af11017b07559c31cae4bc0a4b
  (copied to `artifact/checkpoints/tyflow-2b-sufu/last_model.ckpt`)
- Baseline side: `t5_llm/models/t5gemma2-2b_sufu/checkpoint_sweep_steps_v3_20260730/epoch_9_step_175`
  (model.safetensors SHA256 e7a865fde37c0888577a...; copied to
  `artifact/checkpoints/baseline-2b-sufu/`).

## Paper updates backed by this package

- Table 1 SuFu 2B rows: T5Gemma2-2B 25.86/37.93/6.66/71.21,
  TyFlow-2B 36.21/48.28/5.53/0.00 (both rows now array-backed).
- Appendix D 2B SuFu block: real intervals and paired tests from
  `2b_sufu_paired_stats_optionB.json` (only CER significant,
  p = 6.94e-18; pass@1 p = 0.286, pass@10 p = 0.307, FSP p = 0.362).
- RQ1 prose and decoder-only comparison passage updated accordingly
  (pass@10 improvement range 6.90--20.69; TyFlow-2B solves 21).

## Files

Score records (with per-task arrays), generation logs, and the paired-statistics computation
(`scripts/compute_2b_sufu_paired_stats_20260915.py`, method matches the
appendix: exact two-sided McNemar / sign tests, Wilson and t intervals).
SHA256SUMS covers everything.
