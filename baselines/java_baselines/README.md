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
contract with Repilot. The constraint guarantees context-free syntactic
validity only, not Java type correctness.

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
For identifier-like tokens it queries the modified JDT server; punctuation
and Java keywords use Repilot's original trivial-feasibility shortcut.

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
