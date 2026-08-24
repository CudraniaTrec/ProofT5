# Separate-Benchmark Half Split (2026-07-31)

The split uses seed `273567`, has no validation set, and keeps every test
benchmark in a separate file and ProofT5 task.

| Language | Training | Original test | External test |
| --- | ---: | ---: | ---: |
| Java | 673 | MBJP 67 | HumanEval 66 |
| SuFu | 252 | Original 58 | Synthetic 20 |

Java training contains 541 original MBJP train rows, 67 former MBJP valid
rows, and 65 randomly selected HumanEval rows. SuFu training contains 232
original rows and 20 randomly selected synthetic rows.

The odd-sized HumanEval expansion uses floor division for training. Thus 65
rows enter training and 66 remain for testing. `split_manifest.json` freezes
all external train/test IDs.

## Plain T5Gemma2

Training:

```text
t5_llm/data/java_mbjp_humaneval_half_train_t5.json
t5_llm/data/sufu_original_synthetic_half_train_t5.json
```

Testing:

```text
t5_llm/data/java_mbjp_original_test_t5.json
t5_llm/data/java_humaneval_half_test_t5.json
t5_llm/data/sufu_original_test_t5.json
t5_llm/data/sufu_synthetic_half_test_t5.json
```

Dataset names accepted by `finetune_t5gemma2.py`:

```text
java_expanded_train
java_mbjp_test
java_humaneval_test
sufu_expanded_train
sufu_original_test
sufu_synthetic_test
```

The four test names must be used with `--generate_only` and an explicit
checkpoint. Training datasets have empty test splits; with no validation rows,
training uses a fixed epoch count and does not select checkpoints on test
performance.

## ProofT5

Training:

```text
Utils/data/mbjp_humaneval_half_train_t5gemma2_20260731
Utils/data/sufu_original_synthetic_half_train_t5gemma2_20260731
```

Testing:

```text
Utils/data/mbjp_original_test_t5gemma2_20260731
Utils/data/humaneval_half_test_t5gemma2_20260731
Utils/data/sufu_original_test_t5gemma2_20260731
Utils/data/sufu_synthetic_half_test_t5gemma2_20260731
```

The four test tasks have empty train/valid splits and
`"evaluation_only": true`. A scorer therefore cannot silently combine the
original and external benchmark results.

## Rebuild

```bash
source scripts/runtime_env.sh
/data2/x/hzc/.uv-envs/prooft5-t5gemma-py313/bin/python \
  scripts/build_half_split_expansion.py
```

The builder refuses to overwrite existing outputs.
