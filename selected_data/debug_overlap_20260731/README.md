# Latest complete training sets (2026-07-31)

The latest data is treated as one complete training set:

- Java: 706 training rows.
- SuFu: 281 training rows.

The four benchmark test tasks remain separate and unchanged:

- original MBJP (67)
- held-out HumanEval-Java half (66)
- original SuFu (58)
- held-out synthetic SuFu half (20)

There is no newly divided validation set. Validation is empty for both tasks.
The benchmark test tasks remain external to these training tasks.

## ProofT5

The complete training data is stored across `train.pkl` plus an additional
storage file named `debug.pkl` for compatibility with the existing loader:

- `Utils/data/mbjp_humaneval_half_train_t5gemma2_20260731`
- `Utils/data/sufu_original_synthetic_half_train_t5gemma2_20260731`

`--include_debug` is the legacy CLI spelling required to load all 706 or 281
training rows. It does not denote a separate evaluation category. Use
`--model_output_task` to give the resulting model an explicit output name.

## Plain T5Gemma2

The corresponding complete training JSON files are:

- `t5_llm/data/java_mbjp_humaneval_half_train_t5.json`
- `t5_llm/data/sufu_original_synthetic_half_train_t5.json`

The same legacy `--include_debug` option loads every training row. The ordinary
T5Gemma2 baselines are already trained and are not retrained by the ProofT5
full-training-set runs.
