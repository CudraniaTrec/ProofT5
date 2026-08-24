# Selected Java and SuFu Expansion (2026-07-31)

This package contains only the expansion selected for the next experiment:

```text
Java HumanEval: 131 held-out test programs
Synthetic SuFu: 40 held-out test programs (22 list + 18 structural)
```

MathQA, McEval, and NaturalCodeBench are not part of this selected package.
No row in this package is a training or validation example.

## Human-Readable Records

`java_humaneval_131.json` uses:

```text
task_id, language, description, prompt, program, test
```

`sufu_synthetic_40.json` uses:

```text
task_id, language, description, prompt, program, tests, expected_output
```

For Java, `program` is the implementation that passed the existing ProofT5
AST-to-Coq-to-token-to-Java round trip and the official HumanEval test.

For SuFu, `program` is the complete program, including the fixed library
prefix and task implementation. `tests` contains ten deterministic executions
per task.

## Model-Aligned Records

Plain T5Gemma2:

```text
t5_llm/data/humaneval_external131_test_t5.json
t5_llm/data/sufu_synthetic40_test_t5.json
```

The Java file matches the field order used by `humaneval_t5.json`:

```text
task_id, prompt, code, test, type
```

The SuFu file matches the field order used by `sufu_t5.json`:

```text
task_id, prompt, code, postfix, tests, output, type
```

Every `type` value is `test`.

ProofT5:

```text
Utils/data/java_humaneval_external_t5gemma2_20260730
Utils/data/sufu_synthetic40_external_t5gemma2_20260731
```

Both tasks have empty `train` and `valid` splits. The SuFu task combines the
previously validated 22-row and 18-row suites without changing any row,
tokenizer, vocabulary, prefix, or target token sequence.

## Rebuild

```bash
source scripts/runtime_env.sh
/data2/x/hzc/.uv-envs/prooft5-t5gemma-py313/bin/python \
  scripts/prepare_selected_expansion_datasets.py
```

The script refuses to overwrite existing outputs.
