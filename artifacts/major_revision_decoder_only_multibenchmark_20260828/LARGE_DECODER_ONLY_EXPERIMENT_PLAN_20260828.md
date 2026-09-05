# Larger decoder-only follow-up (2026-09-02)

This plan covers the selected larger open-weight candidates requested for the
major-revision decoder-only comparison.  It is additive: existing frozen
checkpoints, score files, and the dirty worktree are not overwritten.

## Models

| model | local path | family | generation contract |
|---|---|---|---|
| Qwen3-14B-Base | `/data2/x/hzc/hf_models/Qwen3-14B-Base` | causal | Java prefix continuation; plain tokenizer text |
| Qwen3-30B-A3B-Base | `/data2/x/hzc/hf_models/Qwen3-30B-A3B-Base` | causal MoE | Java prefix continuation; plain tokenizer text |
| Qwen3.6-27B | `/data2/x/hzc/models/qwen/Qwen3.6-27B` | causal | SuFu six-shot prefix continuation; plain tokenizer text |
| OLMo-3-1125-32B | `/data2/x/hzc/hf_models/Olmo-3-1125-32B` | causal | Java prefix continuation; plain tokenizer text |

The Base rows are not fine-tuned or adapted.  Qwen3-32B and the unselected
Qwen3.5/Qwen3.8 variants remain archived diagnostics rather than headline
comparisons.  The selected rows use the same no-I/O Java inputs, the same
frozen scorer, one greedy candidate, and fresh output tags.  Qwen3.6-27B is the
single newer-generation Qwen representative selected for the additive SuFu
six-shot follow-up.

## Java protocol

For MBJP, HumanEval-Java v15, and GFG-v13, run both zero-shot and corrected
synthetic three-shot (`--few_shot_style synthetic_minimal --few_shot_k 3`).
The synthetic examples are the fixed identity, increment, and empty-string
tasks already specified in `SYNTHETIC_THREESHOT_SPEC.md`; they are not sampled
from any benchmark.  `--reject_io_examples` is mandatory.  The model message
contains the target task specification but no target test, expected output, or
JavaDoc I/O example.

Representative zero-shot command (change the dataset, score task, and tag per
benchmark/model):

```bash
/data2/x/hzc/.uv-envs/prooft5-t5gemma-py313/bin/python \
  baselines/java_baselines/run_decoder_only_zero_few_shot.py \
  --dataset_json <no-io-test-json> --dataset_split test \
  --score_task <authoritative-score-task> --score_split test \
  --output_tag <new-output-tag> --candidates 1 --greedy_first \
  --few_shot_k 0 --completion_mode prefix_completion \
  --reject_io_examples --backend hf --model <local-model-path> \
  --model_family causal --dtype bf16 --local_files_only --no_chat_template
```

For the corrected F3 condition, use the same command with
`--few_shot_style synthetic_minimal --few_shot_k 3`.  Qwen3-32B uses
`--completion_mode full_source` is retained only for the archived post-trained
Qwen3-32B diagnostic; selected Base rows use `prefix_completion` as
code-continuation controls.

## SuFu protocol

SuFu uses the 58-row frozen test split and its native parser/executor scorer.
The paper-facing F3 is a capability-oriented, high-information full-source
condition: the complete target description and public type/helper prefix are
shown, rich training examples are provided, and the model is instructed to
return a complete program.  The earlier source-prefix/no-chat condition is
retained only as a restricted-format control.  The original paper-facing F3
uses three complete training-split programs.  The additive selected follow-up
uses six complete, more realistic training-split programs selected by task ID from
`inputs/sufu_few_shot_train_only_noio_notest_20260902.json`; see
`SUFU_REALISTIC_TRAINLIKE_THREESHOT_SPEC.md`.  They contain nested data,
recursive helpers, and compressed alignment, but no tests, outputs, target
suffixes, or test-task rows.  The train-only file is generated from the legacy
mixed source by `scripts/build_sufu_train_only_fewshot_20260902.py`, and the
runner rejects explicit test/valid/debug rows.  The scorer remains the only
component that reads the frozen `tests` and `output` fields.  The target block ends with the
explicit `COMPLETE SUFU SOURCE:` marker inserted by the current runner;
pre-boundary outputs are retained only as diagnostics.

```bash
/data2/x/hzc/.uv-envs/prooft5-t5gemma-py313/bin/python \
  baselines/java_baselines/run_decoder_only_sufu.py \
  --dataset_json t5_llm/data/sufu_original_test_t5.json \
  --score_task sufu_original_test_t5gemma2_20260731 --score_split test \
  --output_tag <new-output-tag> --prompt_mode full_source \
  --few_shot_dataset artifacts/major_revision_decoder_only_multibenchmark_20260828/inputs/sufu_few_shot_train_only_noio_notest_20260902.json \
  --few_shot_ids incre-tests-synduce-constraints-sortedlist-parallel_max2,incre-tests-synduce-zipper-list_sum,incre-tests-synduce-constraints-all_positive-sndmax \
  --few_shot_k 3 --guidance_profile high_information --candidates 1 --greedy_first --max_tokens 2048 \
  --backend hf --model <local-model-path> --model_family causal \
  --dtype bf16 --local_files_only --no_chat_template
```

## Status

The hand-written and train-like SuFu examples have been parser- and type-check
validated.  The selected Hugging Face repositories contain verified complete
snapshots.  The Base-model Java 8-condition matrices are complete; Qwen3.6's
chat-thinking/full-source Java rows are retained only as interface diagnostics
pending a prefix/no-chat rerun.  Corrected SuFu boundary reruns are additive.
Every condition generates one greedy candidate
for every frozen task:
MBJP 67, HumanEval-Java 16, GFG-v13 103, and SuFu 58.  The resulting counts
are consolidated in `MASTER_COMPARISON_TABLE_HIGHINFO_SUFU_20260828.md`; the
read-only completeness check is `scripts/audit_large_matrix_final_20260901.py`.

The audit reports explicit runtime/interface failures without treating them as
missing evaluations: Qwen3-30B-A3B-Base has three GFG timeouts (one zero-shot,
two F3), OLMo-3-1125-32B has two GFG timeouts in each condition, and
Qwen3.8-27B has two SuFu interface-marker outputs in each condition.  All
corresponding task IDs were still attempted and remain in the denominator.

For an immediate pipeline check, the existing complete CodeGemma checkpoint
was run with the same SuFu-native protocol after fixing prompt-copy cleaning:
synthetic F3 scores 0/58 with 56/58 compilation errors.  The separately
generated zero-shot control also scores 0/58 (57/58 compilation errors before
the cleaner-only rerun).  These diagnostic results are in the two
`decoder_codegemma_sufu_syn*` score files and are not used as results for the
four larger candidates.
