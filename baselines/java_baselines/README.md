# Java baselines for the TOSEM Major Revision

This directory adapts three public baseline families to the frozen ProofT5
Java evaluation contract. It does not alter checkpoints, benchmark tests,
existing outputs, score JSONs, or manuscript tables.

The upstream repositories and exact commits are recorded in
`UPSTREAM_LOCK.json` and are downloaded under the gitignored
`third_party/baselines/` directory. Restore or verify those checkouts with:

```bash
python3 baselines/java_baselines/fetch_upstreams.py
python3 baselines/java_baselines/fetch_upstreams.py --verify-only
```

`bootstrap_envs.sh` runs the restore command before installing SynCode.

## Frozen T5Gemma2 checkpoints

The runners also accept the three frozen ordinary T5Gemma2 encoder-decoder
checkpoints in the 2026-08-24 result package. Those checkpoint directories do
not contain tokenizer files, so pass the retained base tokenizer explicitly:

```text
--tokenizer Utils/models/t5gemma-2-1b-1b --model_family seq2seq
```

`run_frozen_t5gemma_baseline.sh` binds each benchmark to the correct frozen
checkpoint, inspectable generation dataset, and authoritative scorer task. For
example, a one-problem Repilot check is:

```bash
PROOFT5_BASELINE_GPU=0 PROOFT5_BASELINE_CANDIDATES=1 \
  baselines/java_baselines/run_frozen_t5gemma_baseline.sh \
  repilot gfg repilot_gfg_check --indices 0
```

For a formal ten-candidate run, omit the candidate override and `--indices`.
The wrapper uses a greedy rank-0 candidate followed by nine fixed-seed sampled
candidates, a 1024-token cap, temperature 0.8, and the frozen seed schedule.
SynCode additionally uses a 240-second fail-closed per-candidate timeout. The
wrapper refuses to overwrite an existing output tag. It also defaults
`OMP_NUM_THREADS` and `MKL_NUM_THREADS` to one for SynCode because concurrent
rank shards otherwise oversubscribe CPU mask operations; override with
`PROOFT5_SYNCODE_CPU_THREADS` only for a recorded profiling run.

Long SynCode runs can be partitioned with `--indices` and
`--candidate_ranks 0,2,4,6,8` (or the complementary ranks) plus `--resume`.
Rank sharding is operational only: the seed remains based on the global task
and rank, so it does not change any candidate's declared generation settings.

For SynCode with T5Gemma2, use the compatibility environment created by
`bootstrap_envs.sh`. SynCode's upstream Transformers 4.53.2 pin predates the
T5Gemma2 architecture; the original pinned environment remains intact while
the separate `prooft5-syncode-t5gemma-py312` environment uses Transformers
5.12.1.

The encoder-decoder adaptation preserves the checkpoint's prefix-to-complete-
source training contract while avoiding needless prompt regeneration. The
benchmark prefix is both encoder input and a fixed decoder prefix; SynCode and
Repilot constrain/prune only the unknown suffix while parsing/updating the
combined Java file. SynCode's upstream `grammar_mask` is an over-approximation;
its unmodified path falls back to unconstrained decoding after parser failure.
The production Java adapter instead fails closed and records that event; the
upstream fallback remains available only as a labelled diagnostic. The iterative runner uses
the raw benchmark prefix for its initial call; later compiler-feedback prompts
are out of the checkpoint's training distribution and must be reported as a
matched-weight diagnostic, not as the strongest possible instruction-tuned
repair baseline.

## Shared contract

Every runner accepts an inspectable JSON dataset and separately names the
authoritative ProofT5 scoring task. Before generation it aligns every prompt
to `Utils/data/<task>/<split>.pkl` by exact complete test-harness identity and
fails closed unless the mapping is one-to-one. This handles the known
HumanEval JSON/pickle ordering difference without exposing tests to a model.
Candidates are written to the existing scorer layout:

```text
Utils/output/<score_task>_<split>_ans/<output_tag>/<problem>_<rank>.txt
```

Each candidate also has a trajectory JSON, and each run has a manifest with
dataset hashes and generation settings. Existing directories are never
overwritten; use a new tag, or `--resume` to fill missing candidate slots.

## Minimal-information few-shot control (HumanEval/MBJP)

For the corrected three-shot HumanEval-Java and MBJP controls, use
`run_decoder_only_zero_few_shot.py --few_shot_style synthetic_minimal --few_shot_k 3`.
This mode synthesizes three complete, tiny Java programming tasks inside the
runner. Their imports, JavaDoc, class/method declaration, and complete source
follow the benchmark's Java prompt shape, but their semantics are generic
identity/increment/empty-string checks. They are not sampled from MBJP,
HumanEval, GFG, or SuFu and do not read or serialize any training example,
test, or I/O field. The target prompt remains unchanged. A representative
invocation is:

```bash
/data2/x/hzc/.uv-envs/prooft5-t5gemma-py313/bin/python \
  baselines/java_baselines/run_decoder_only_zero_few_shot.py \
  --dataset_json <no-io-test-json> --dataset_split test \
  --few_shot_style synthetic_minimal --few_shot_k 3 \
  --score_task <authoritative-task> --score_split test \
  --output_tag <new-tag> --candidates 1 --greedy_first \
  --reject_io_examples --model <local-checkpoint> --model_family causal \
  --local_files_only
```

The corresponding zero-shot condition is the same command with
`--few_shot_k 0`. The earlier `minimal_format` (format-only empty skeleton)
condition is retained as a diagnostic artifact, but is not the corrected
three-shot protocol. Use a fresh output tag for every condition; score only
after all task outputs are present.

## SynCode

Create the isolated Python 3.12 environment (SynCode does not support the
project's Python 3.13 environment):

```bash
baselines/java_baselines/bootstrap_envs.sh
```

Example dry run on frozen MBJP:

```bash
/data2/x/hzc/.uv-envs/prooft5-syncode-py312/bin/python \
  baselines/java_baselines/run_syncode.py \
  --dataset_json t5_llm/data/java_mbjp_original_test_t5.json \
  --score_task mbjp_original_test_t5gemma2_20260731 \
  --score_split test --output_tag syncode_mbjp_pilot --dry_run
```

Remove `--dry_run` and add `--model /path/to/local-causal-model`. By default,
the exact benchmark Java prefix is the causal-model input and SynCode parses
that prefix together with every generated suffix token. This avoids asking the
model to regenerate the prompt's Javadoc comments and aligns its completion
contract with Repilot. The constraint checks context-free syntax only, not Java
type correctness. The default matched mode is proposal-preserving rejection:
it samples from the ordinary top-k/top-p distribution first and resamples only
if the SynCode mask rejects that proposal. Pass
`--no-proposal_preserving_rejection` only for an explicitly labelled upstream-
style pre-mask diagnostic. Parser failures are fail-closed rather than silently
converted to unconstrained generation.

For a frozen T5Gemma2 checkpoint, also provide its base tokenizer and use the
compatibility Python shown above. The runner automatically selects
`AutoModelForSeq2SeqLM`, fixes the known benchmark text as the decoder prefix,
and constrains the generated suffix while parsing the combined Java file.
The adapter incrementally caches token-id-to-byte decoding instead of copying
and decoding the complete prefix at every step; this does not cache parser
states or alter masks. Pass `--disable_incremental_input_decode` for the exact
upstream decoding path. Trajectories separate SynCode constraint time from
non-constraint generation time and record both per decoder step.

The Java adapter also repairs an upstream mask-store hole for standalone
whitespace tokens: pure-whitespace pieces are restored only when the current
parse result explicitly permits ignored `WS`. Training-only soundness evidence
is frozen under `artifacts/major_revision_mbjp_baselines_20260825/`.

For the explicitly labelled paper-facing safe portfolio, combine the matched
ordinary and upstream-style SynCode output trees with
`build_compile_safe_constraint_portfolio.py`. It retains the ordinary rank
unless standalone `javac` rejects it and accepts the corresponding SynCode
rank. The selector never executes benchmark tests, keeps the ten-candidate
budget, and must report both generation arms; it is not unmodified SynCode.

## Repilot-style completion-engine pruning

The original Repilot CLI is tied to Defects4J, CodeT5/InCoder, Python 3.10,
and a modified Eclipse JDT language server. `run_repilot.py` retains its core
token-pruning policy and `newCompletion` protocol but adapts the task loader,
project wrapper, model loader, output format, and provenance to these Java
generation benchmarks. It must be described as a Repilot adaptation, not an
unchanged execution of the Defects4J repair tool.

Build the downloaded modified JDT server:

```bash
baselines/java_baselines/build_jdtls.sh
```

Then run a one-problem pilot before a full experiment:

```bash
/data2/x/hzc/.uv-envs/prooft5-t5gemma-py313/bin/python \
  baselines/java_baselines/run_repilot.py \
  --dataset_json t5_llm/data/java_mbjp_original_test_t5.json \
  --score_task mbjp_original_test_t5gemma2_20260731 \
  --score_split test --output_tag repilot_mbjp_pilot \
  --model /path/to/local-causal-model --local_files_only \
  --indices 0 --candidates 1 --max_new_tokens 256
```

The adapter generates the suffix following the benchmark's exact Java prefix.
Original Repilot queries modified JDT for identifier-like tokens but uses a
trivial-feasibility shortcut for punctuation and Java keywords; reproduce that
policy with `--jdt_query_policy upstream_trivial_bypass` (the runner and frozen
launcher default). The optional `every_token` diagnostic sends every non-EOS
candidate token to JDT and must be labeled as an all-token Repilot/JDT
adaptation, not unchanged upstream Repilot. Each trajectory records LM time, JDT query/update time,
query count, rejected candidates, and aggregate/per-output-token costs.

For attribution only, the frozen launcher also accepts `ordinary`. This runs
the identical forced-prefix, greedy-rank-0, fixed-seed sampling loop with JDT
disabled. It is a matched decoder control for separating pruning effects from
the frozen ordinary row's ten-beam search; it is not an additional strong
baseline column.

## Controlled iterative refinement

This runner distills LLMLOOP to the reviewer-requested mechanism: initial
generation followed by at most two repair calls using only `javac`
diagnostics. JUnit, hidden benchmark tests, PMD, EvoSuite, coverage, and
mutation feedback are deliberately excluded.

It accepts either a local Hugging Face model or an OpenAI-compatible local
server such as vLLM:

```bash
/data2/x/hzc/.uv-envs/prooft5-t5gemma-py313/bin/python \
  baselines/java_baselines/run_iterative_refinement.py \
  --dataset_json t5_llm/data/java_mbjp_original_test_t5.json \
  --score_task mbjp_original_test_t5gemma2_20260731 \
  --score_split test --output_tag refine_mbjp_pilot \
  --backend openai --base_url http://127.0.0.1:8000 \
  --model local-model-name --indices 0 --candidates 1
```

Use `--backend hf --model /path/to/model --local_files_only` for direct local
loading. `--backend scripted` is reserved for deterministic pipeline tests.

## Scoring

After a complete ten-candidate run, use the unchanged scorer:

```bash
/data2/x/hzc/.uv-envs/prooft5-t5gemma-py313/bin/python score_java_no_write.py \
  --task mbjp_original_test_t5gemma2_20260731 --split test \
  --output_tag <output_tag> --pass_at_k 10 --workers 64 --timeout 10 \
  --decoder <syncode|repilot_jdt|compiler_feedback> \
  --json_out tmp/<output_tag>_score.json
```

The iterative runner never reads or sends the `test` field to the model; the
test harness is used only for pre-run alignment and later by the frozen scorer.

Summarize the recorded model/JDT/repair cost after generation with:

```bash
/data2/x/hzc/.uv-envs/prooft5-t5gemma-py313/bin/python \
  baselines/java_baselines/summarize_trajectories.py \
  --output_dir Utils/output/<task>_test_ans/<output_tag> \
  --json_out tmp/<output_tag>_cost.json
```

For a defensible comparison, use the same local causal-model checkpoint,
maximum generated length, sampling parameters, candidate count, and random
seed schedule for SynCode and Repilot. For iterative refinement, report both
the per-call cap and the observed total calls/tokens; every trajectory records
these values. Do not select a checkpoint or repair count using hidden tests.

## Verification performed on 2026-08-23

- All four downloaded repositories remained clean at the commits in
  `UPSTREAM_LOCK.json` after setup.
- The modified Eclipse JDT server built successfully on Temurin 17. Its
  `newCompletion` endpoint accepted `System`, rejected a fabricated identifier,
  and returned normalized source/target continuations.
- The isolated SynCode 0.4.16 environment loaded the built-in Java grammar
  with its incremental LALR parser.
- A local 0.5B causal checkpoint completed direct-Hugging-Face smoke calls for
  both the iterative client and the Repilot/JDT generation path.
- The repository test suite passed 64 tests after the adapter additions. Only explicitly
  labelled, one-candidate smoke outputs on selected problems were generated and
  scored; no frozen result, checkpoint, or manuscript file was changed.

## Additional T5Gemma2 verification on 2026-08-24

- All three retained generation datasets (67 MBJP, 16 HumanEval-Java v15, and
  103 GFG v13 tasks) aligned one-to-one with their frozen scorer pickles for all
  three runners.
- The frozen GFG ordinary checkpoint loaded through the shared encoder-decoder
  runtime. Repilot/JDT generated a complete compiling candidate for problem 0
  and made real completion-engine queries; the candidate failed the hidden
  functional test, as recorded by a selected-problem scorer run.
- The same checkpoint completed a three-call controlled refinement trajectory
  on GFG problem 47 (`javac` initial call plus two repairs). No hidden test was
  exposed. All three attempts retained the same unclosed-comment error,
  illustrating why this matched-weight refinement is diagnostic: the frozen
  prefix-to-source model is not instruction-tuned for repair prompts.
- The focused baseline suite passes 12 tests. Full repository collection is
  independently blocked by duplicate tree-sitter test module names under
  `SuFu/` and `Utils/`.

These are integration checks, not paper-facing benchmark accuracy results.

## Checkpoint-free online-output replay

`export_online_prompt_bundle.py` produces a fail-closed bundle containing only
the selected task prompts and hashes. Hidden test harnesses are used internally
for scorer-index alignment, but they are not serialized. An online model can
return one suffix per row, after which `run_online_replay.py` can independently
exercise `javac`, full SynCode parsing, SynCode token masks, Repilot/JDT token
feasibility, and the existing candidate-output contract.

SynCode token-mask replay and Repilot replay require only a local tokenizer;
they do not load model weights. Text replay verifies that the constraint
engines accept or reject the supplied token path. It is not a substitute for
the final generation experiment, because an online text API does not expose
the per-token logits that SynCode and Repilot must alter during sampling. The
iterative runner can, by contrast, replay complete online responses directly,
including an actual compiler-error/repair round.

The 2026-08-23 smoke used one Codex sub-agent on six test-free prompts: two
each from MBJP, HumanEval-Java, and TransCoder-GFG. All six compiled, passed
their selected hidden functional tests, passed full SynCode parsing, passed
SynCode token-mask replay, and were accepted by Repilot/JDT. Repilot issued 54
real completion queries. The SynCode and Repilot negative probes were both
rejected. A separate compiler-feedback candidate followed the compile sequence
`false -> true` and then passed its selected functional test. These are
one-candidate readiness checks, not benchmark accuracy measurements. The
scratch outputs were deliberately removed during the final repository cleanup;
this section preserves the verification summary but is not a benchmark result
or paper-facing artifact.

This smoke exposed and fixed one important integration bug: generating an
entire source file caused SynCode's token mask to reject a tokenizer token that
contained the start of a Javadoc block. The production adapter now always
uses the exact Java benchmark prefix as the causal-model context and constrains
only its generated suffix, while parsing the combined prefix and suffix.

The adapter also adds a ProofT5 cache guard around SynCode. Upstream names a
mask store using only tokenizer class and vocabulary size; the guard binds it
to a SHA-256 fingerprint of the complete token-to-id vocabulary and fails
closed on a mismatch. Reuse is therefore safe for a fine-tuned checkpoint with
the identical tokenizer; a changed tokenizer must pass `--rebuild_mask_store`.
