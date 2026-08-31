# Larger decoder-only follow-up (2026-08-28)

This plan covers the four larger open-weight candidates requested for the
major-revision decoder-only comparison.  It is additive: existing frozen
checkpoints, score files, and the dirty worktree are not overwritten.

## Models

| model | local path | family | generation contract |
|---|---|---|---|
| Qwen3-14B-Base | `/data2/x/hzc/hf_models/Qwen3-14B-Base` | causal | Java prefix continuation; plain tokenizer text |
| Qwen3-30B-A3B-Base | `/data2/x/hzc/hf_models/Qwen3-30B-A3B-Base` | causal MoE | Java prefix continuation; plain tokenizer text |
| Qwen3-32B | `/data2/x/hzc/hf_models/Qwen3-32B` | causal, post-trained | complete Java source; plain tokenizer text for matched control |
| OLMo-3-1125-32B | `/data2/x/hzc/hf_models/Olmo-3-1125-32B` | causal | Java prefix continuation; plain tokenizer text |

The Base rows are not fine-tuned or adapted.  Qwen3-32B is reported separately
because it is a post-trained checkpoint rather than a Base checkpoint.  All
four use the same no-I/O Java inputs, the same frozen scorer, one greedy
candidate for the initial pass, and a fresh output tag.

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
`--completion_mode full_source` because its checkpoint is post-trained; the
other three use `prefix_completion` as code-continuation Base controls.

## SuFu protocol

SuFu uses the 58-row frozen test split and its native parser/executor scorer.
The paper-facing F3 is a capability-oriented, high-information full-source
condition: the complete target description and public type/helper prefix are
shown, rich training examples are provided, and the model is instructed to
return a complete program.  The earlier source-prefix/no-chat condition is
retained only as a restricted-format control.
Each of the three demonstrations is a complete, more realistic training-split
program selected by task ID from
`inputs/sufu_few_shot_train_noio_notest.json`; see
`SUFU_REALISTIC_TRAINLIKE_THREESHOT_SPEC.md`.  They contain nested data,
recursive helpers, and compressed alignment, but no tests, outputs, target
suffixes, or test-task rows.  The scorer remains the only component that reads
the frozen `tests` and `output` fields.

```bash
/data2/x/hzc/.uv-envs/prooft5-t5gemma-py313/bin/python \
  baselines/java_baselines/run_decoder_only_sufu.py \
  --dataset_json t5_llm/data/sufu_original_test_t5.json \
  --score_task sufu_original_test_t5gemma2_20260731 --score_split test \
  --output_tag <new-output-tag> --prompt_mode full_source \
  --few_shot_dataset artifacts/major_revision_decoder_only_multibenchmark_20260828/inputs/sufu_few_shot_train_noio_notest.json \
  --few_shot_ids incre-tests-synduce-constraints-sortedlist-parallel_max2,incre-tests-synduce-list-last,incre-tests-synduce-ptree-maxsum \
  --few_shot_k 3 --guidance_profile high_information --candidates 1 --greedy_first --max_tokens 1024 \
  --backend hf --model <local-model-path> --model_family causal \
  --dtype bf16 --local_files_only --no_chat_template
```

## Status

The hand-written and train-like SuFu examples have been parser- and type-check
validated.
The four Hugging Face repositories were started with resumable parallel
transfers.  At the latest check, the local directories contain only partial
weight shards because the outbound proxy began returning TLS EOF/503 errors;
the directories are therefore explicitly not treated as usable checkpoints.
No score is recorded until a model directory contains all weight shards and a
one-row generation smoke test plus the full scorer pass both succeed.

For an immediate pipeline check, the existing complete CodeGemma checkpoint
was run with the same SuFu-native protocol after fixing prompt-copy cleaning:
synthetic F3 scores 0/58 with 56/58 compilation errors.  The separately
generated zero-shot control also scores 0/58 (57/58 compilation errors before
the cleaner-only rerun).  These diagnostic results are in the two
`decoder_codegemma_sufu_syn*` score files and are not used as results for the
four larger candidates.
