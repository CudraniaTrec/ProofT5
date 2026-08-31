# CodeGemma-2B with the frozen ProofT5 rule representation (v5)

This directory records the complete no-I/O CodeGemma control in which the
CodeGemma-2B backbone is trained to predict the frozen ProofT5 DSL/rule
sequence.  The natural-language side is retokenized with the local CodeGemma
tokenizer; the rule vocabulary, grammar, Java harness, and 67-task MBJP test
identity are unchanged.  v5 uses syntax pruning only (`disable_coq_check=true`)
and ten candidates per task.

The v5 run has five pretraining passes over 9,856 rows, followed by thirty
Java passes over 673 rows.  It intentionally preserves the earlier v4/v5
checkpoints and candidate trees.  All 670 candidates were generated for every
checkpoint below; no checkpoint was selected using a validation split, because
the available evaluation is the frozen 67-task test split.

| checkpoint | pass@1 | pass@10 | compile errors | timeouts |
|---|---:|---:|---:|---:|
| epoch 5 | 11/67 (16.42%) | 30/67 (44.78%) | 165/670 | 4 |
| epoch 10 | 17/67 (25.37%) | 27/67 (40.30%) | 138/670 | 3 |
| epoch 15 | 15/67 (22.39%) | 27/67 (40.30%) | 141/670 | 6 |
| epoch 20 | 16/67 (23.88%) | 27/67 (40.30%) | 140/670 | 5 |
| epoch 25 | 15/67 (22.39%) | 27/67 (40.30%) | 132/670 | 5 |
| final | 12/67 (17.91%) | 25/67 (37.31%) | 143/670 | 3 |

For the same sanitized prompts and scorer, the raw CodeGemma-2B zero-shot
control obtains 29/67 pass@1 and 48/67 pass@10.  Thus v5 is a reproducible
negative result, not a result that satisfies the intended parity target.  A
protocol audit found that raw CodeGemma automatically receives a BOS token,
whereas v5 was trained without one.  The corrected BOS-matched retraining is
recorded under `major_revision_codegemma_rules_20260827_bos_v1` and must be
evaluated separately rather than mixed with these scores.

Authoritative score JSONs are `mbjp_syntax_score*.json`; the raw decoder-only
control is `../major_revision_decoder_only_noio_20260826/scores/codegemma2b_noio_zero.json`.
