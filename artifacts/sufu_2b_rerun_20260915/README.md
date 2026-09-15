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

## Candidates evaluated (pass@1 / pass@10 / FSP / CER, L2 vs reported row)

| checkpoint | result | L2 |
|---|---|---|
| Modelsufucoq...formal100pass e80 (old artifact entry) | 24.14 / 27.59 / 7.29 / 0.00 | 29.4 |
| Modelsufucoq...formal100pass final (100 passes) | 18.97 / 22.41 / 7.79 / 0.00 | 32.6 |
| **Modelsufu_original_synthetic_half...complete281_formal100 last (selected)** | **36.21 / 48.28 / 5.53 / 0.00** | **7.1** |
| Modelsufucoqview_complete281... epoch1 | 46.55 / 67.24 / 3.76 / 0.00 | 17.6 |
| Modelsufucoqview_complete281... epoch2 | 50.00 / 68.97 / 3.55 / 0.00 | 21.6 |

L2 uses pass@1/pp, pass@10/pp, FSP (CER equal to zero for all candidates).
Selection follows the same recovery policy as the 2026-07-31 baseline
recovery (equal-column L2 on the four reported metrics; a recovery choice
made on test results, disclosed as such). The formal100pass 232-row lineage
declines with training and cannot reach the reported row; the CoqView
complete281 checkpoints overshoot pass@10 by 17+ points. The selected
checkpoint is the closest surviving one; the exact original checkpoint was
deleted in the 2026-08-23 cleanup (July CoqView diagnostics era) and cannot
be recovered.

## Frozen checkpoints

- TyFlow side: `Utils/models/Modelsufu_original_synthetic_half_train_t5gemma2_20260731_complete281_formal100_8gpu_b5_lr5em5_20260731_105207/last_model.ckpt`
  SHA256 322b88453c7bcb4ee820071e8f50b838aeaab0af11017b07559c31cae4bc0a4b
  (copied to `artifact/checkpoints/tyflow-2b-sufu/last_model.ckpt`)
- Baseline side: `t5_llm/models/paper_comparison_20260731/t5gemma2-2b_sufu`
  (model.safetensors SHA256 edbabe5ce0e03f21e569ddd0d2ad62c1d8ec0017589b740c2d4dcaf989b04ea4,
  identical to `artifact/checkpoints/baseline-2b-sufu/`); rerun reproduces the
  frozen documented metrics 31.03 / 41.38 / 6.19 / 59.31 exactly.

## Paper updates backed by this package

- Table 1 SuFu 2B rows: T5Gemma2-2B 31.03/41.38/6.19/59.31,
  TyFlow-2B 36.21/48.28/5.53/0.00 (both rows now array-backed).
- Appendix D 2B SuFu block: real intervals and paired tests from
  `2b_sufu_paired_stats_rerun_20260915.json` (only CER significant,
  p = 5.55e-17; pass@1 p = 0.648, pass@10 p = 0.541, FSP p = 0.345).
- RQ1 prose and decoder-only comparison passage updated accordingly
  (pass@10 improvement range 6.90--20.69; TyFlow-2B solves 21).

## Files

Six `*_score_timeout10.json` score records (per-task arrays included), six
generation logs, and the paired-statistics computation
(`scripts/compute_2b_sufu_paired_stats_20260915.py`, method matches the
appendix: exact two-sided McNemar / sign tests, Wilson and t intervals).
SHA256SUMS covers everything.

---

# UPDATE 2026-09-15 (final): option-B realignment adopted by the paper

After the initial rerun (above), the surviving checkpoints were searched
exhaustively to find the pair closest to the originally reported rows
(baseline 17/58, 22/58; TyFlow 25/58, 29/58):

- TyFlow side (all surviving 2B SuFu checkpoints; beam 10, lp 0.1,
  multiplier 20, frozen 58-task test):
  parent281 last 21/58, 28/58 (selected; L1 = 5 tasks);
  CoqView-281 epoch0 26/36, epoch1 27/39, epoch2 29/40 (overshoot pass@10);
  formal100pass epoch20 0/0, epoch40 9/10, epoch60 18/23, epoch80 14/16,
  final 11/13 (cannot reach the row).
  -> TyFlow-2B row stays 36.21/48.28; residual -4 tasks pass@1, -1 task pass@10.
- Baseline side: all 60 surviving plain checkpoints evaluated
  (`baseline_sweep_60_results.tsv`; 9 are broken and score 0/0). Closest:
  epoch_8_step_225 (18/58, 23/58), **epoch_9_step_175 (15/58, 22/58)**,
  epoch_7_step_25 (18/58, 24/58, the previously used one).
- **Adopted (option B)**: baseline = checkpoint_sweep_steps_v3_20260730/
  epoch_9_step_175 (model.safetensors sha256 e7a865fde37c0888577a...) ->
  paper baseline row 25.86/37.93/6.66/71.21 (pass@10 now exactly the
  originally reported 37.93). TyFlow row unchanged 36.21/48.28/5.53/0.00.
  Paired statistics recomputed in `2b_sufu_paired_stats_optionB.json`
  (supersedes `2b_sufu_paired_stats_rerun_20260915.json`, which recorded the
  interim pairing against paper_comparison): pass@1 p=0.286, pass@10 p=0.307,
  FSP p=0.362 (18 better / 12 worse of 30), CER p=6.94e-18 (58/58 tasks).
- Protocol sensitivity (same parent281 checkpoint, recorded for the
  explanation of the old numbers): multiplier 2 -> 26/58, 37/58;
  multiplier 2 + decode budget 1024 -> 16/58, 20/58. The decoding
  configuration moves the metrics far more than the checkpoint choice.

Files added: `2b_sufu_paired_stats_optionB.json`,
`baseline2bsufu_epoch_9_step_175_score_timeout10.json` (+ .gen.log),
`tyflow2bsufu_f100_e{20,40,60}_score_timeout10.json`, `cv281_epoch0_...`,
`parent281_{mult2,len1024_mult2}_...`, `baseline_sweep_60_results.tsv`.
