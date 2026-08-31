# Frozen-T5Gemma2 Java strong-baseline protocol (2026-08-24)

## Purpose and comparison boundary

This experiment reuses the three frozen ordinary T5Gemma2 checkpoints and
changes only the inference method. It adds three reviewer-requested comparison
families: SynCode Java grammar masking, a Repilot-style modified-JDT token
pruner, and controlled `javac`-feedback refinement. It does not modify or
select checkpoints, tests, frozen outputs, or the 2026-08-24 result package.

The paper-facing comparison is:

1. frozen ordinary T5Gemma2 (`hf_beam`);
2. the same ordinary T5Gemma2 weights with SynCode;
3. the same ordinary T5Gemma2 weights with the Repilot/JDT adaptation;
4. the same weights with controlled compiler-feedback refinement;
5. frozen ProofT5 (ours).

SynCode and Repilot are matched-weight decoding comparisons. The iterative row
is a matched-weight diagnostic, because the frozen model was trained from a
Java prefix to a complete source file and was not trained to follow repair
instructions. A later instruction-tuned decoder-only experiment is still
needed before calling iterative refinement a strong instruction-following
baseline.

## Frozen inputs

| benchmark | generation rows | ordinary checkpoint | scorer task |
|---|---:|---|---|
| MBJP | 67 | new reruns: archived paper-row recovery checkpoint `paper_comparison_20260731/t5gemma2-2b_mbjp`; prior frozen rows: clean epoch-20 checkpoint | `mbjp_original_test_t5gemma2_20260731` |
| HumanEval-Java v15 | 16 | `t5gemma2-2b_java_mbjp_humaneval_semanticsupport1082_v15_plain_selected_20260822` | `java_humaneval_mbjp_native_semanticsupport_split90_10_t5gemma2_20260822_v15` |
| TransCoder-GFG v13 | 103 | `t5gemma2-2b_java_mbjp_transcoder_gfg_mbjp_native_prompt2164_v13_exposure3_pair_frombase_stage2_selected_20260819` | `java_transcoder_gfg_mbjp_native_prompt_split80_20_t5gemma2_20260819_v13` |

All checkpoints use `Utils/models/t5gemma-2-1b-1b` as their retained
tokenizer. All three generation datasets have been aligned one-to-one with the
authoritative scorer pickles by complete hidden-test identity. Hidden tests are
never serialized into prompts or model messages.

## Predeclared inference budget

- Candidate budget: 10 ordered candidates per task.
- Rank 0: greedy decoding, so pass@1 is not weakened by a random first draw.
- Ranks 1--9: fixed seeds `273567 + task_index * 10 + rank`, temperature
  0.8, top-p 0.95, top-k 50 where the runner supports token-level filtering.
- Output cap: 1024 new decoder tokens per model call.
- SynCode: Java `grammar_mask` mode; the known benchmark text is a fixed
  seq2seq decoder prefix, and the generated suffix is constrained while the
  combined Java file is parsed. Upstream `grammar_mask` can fall back to
  unconstrained decoding after an incremental parse failure; every such
  candidate is counted and reported. Each candidate has a 240-second
  fail-closed generation timeout in addition to the token cap.
- Repilot: modified-JDT `newCompletion` pruning, with the complete seq2seq
  decoder prefix plus generated suffix maintained as the JDT document.
- Iterative refinement: initial prefix-to-source call plus at most two repair
  calls; feedback contains only `javac` diagnostics; each call has the same
  1024-token cap; compilation timeout is 10 seconds.
- Functional scoring: unchanged frozen Java scorer, 10-second candidate
  timeout, same ordered candidate set for pass@1 and pass@10.
- Runtime reporting: wall time, output tokens, JDT query/rejection counts, and
  iterative model/repair calls are taken from trajectory JSONs. The iterative
  method is allowed up to three times the LM-call/output-token budget and must
  therefore be reported with its observed cost, not as compute-matched.

Protocol amendment (2026-08-25): inspection of Repilot upstream confirmed
that it deliberately bypasses JDT for punctuation and Java keywords. Thus the
completed Repilot results below use the upstream-faithful trivial-feasibility
policy; their approximately one-query-per-three-output-token rate is expected,
not a wrapper bug. Production runs retain that policy. The optional
`every_token` diagnostic must receive a new output tag and the label
"all-token Repilot/JDT adaptation." It may not be silently mixed with the main
protocol. Both Repilot policies now record
CUDA-synchronized LM time, JDT time, query counts, and per-output-token cost.
SynCode now records synchronized constraint versus non-constraint time and
uses a mask-equivalent incremental token-byte decoding cache; the original
full-prefix decode remains available as a control.

Implementation audit (2026-08-25): the original adapter's timeout exception
inherited from `Exception`, so SynCode's broad parser-error handler could
swallow a deadline delivered inside parsing. The MBJP run uses a hard deadline
outside that exception hierarchy; a reproducing problem/rank now terminates at
240.0004 seconds and the shard continues. Concurrent SynCode shards also pin
OMP/MKL to one thread after a probe showed severe CPU oversubscription. These
are execution-correctness fixes, not changes to the Java grammar, model,
sampling seeds, token cap, or candidate timeout.

The frozen ordinary row used ten-beam decoding rather than this
greedy-plus-sampling schedule. Therefore absolute paper comparisons are valid
as method-level results, while a causal claim about the constraint alone would
add a plain Hugging Face control using exactly the new sampling schedule.

Protocol amendment (2026-08-25, checkpoint recovery): new MBJP strong-baseline
runs use the already archived checkpoint
`t5_llm/models/paper_comparison_20260731/t5gemma2-2b_mbjp`, SHA-256
`6bf88a87e24d9d04871b79d21af422fec015eaf8ec0c326db2f745ddbe6ae28a`.
The repository's exhaustive 2026-07-30 recovery audit selected this checkpoint
as the closest available complete paper row after evaluating 46 new Java epochs
and the retained inventory. No checkpoint reproduced all paper metrics. Because
that historical recovery selection used MBJP test metrics, it must be labelled
as paper-checkpoint recovery rather than unbiased checkpoint selection; no new
test-based sweep is permitted. Old epoch-20 results remain frozen and are not
silently relabelled as results from this checkpoint.

Protocol amendment (2026-08-25, SynCode soundness gate): the upstream Java CFG
rejects 30/608 known-correct MBJP training programs. Its basic lexer assigns
nested-generic `>>`/`>>>` to shift tokens, and its cast production conflicts with
parenthesized expressions/lambdas. The new conservative parser view splits
generic closers only inside upper-case type arguments and elides completed casts
only for parsing; the cast alternative is disabled in the adapter grammar.
Actual shifts, strings, comments, model input, and emitted Java are unchanged.
This raises full-program training acceptance from 578/608 to 608/608 (107 closer
splits and 26 cast elisions). These are training-only grammar-coverage checks,
not benchmark accuracy tuning. Fresh SynCode results require a new tag and may
replace the old negative row only after token-level replay and full scoring.

Protocol amendment (2026-08-25, SynCode token-mask repair): the upstream
precomputed DFA mask omitted pure-newline T5Gemma tokens after terminals for
which the parse result explicitly permits ignored `WS`. The adapter restores
only pure-whitespace tokenizer pieces in those states; strings and incomplete
lexical terminals remain constrained. The fixed 16-program training sample
passes 1,909/1,909 actual `accept_mask` decisions, and all 23 first-success
ordinary test trajectories replay without a rejected token.

Protocol amendment (2026-08-25, finite-budget preservation): upstream SynCode
masks before sampling, so probability renormalization changes fixed-seed
trajectories even without false pruning. The matched diagnostic therefore uses
proposal-preserving rejection: sample from the ordinary distribution first,
retain a legal proposal, and resample only after a grammar rejection. The
paper-facing compile-safe variant retains the ordinary rank unless standalone
`javac` rejects it and accepts the corresponding upstream-style SynCode rank.
This selector never executes benchmark tests, keeps ten final candidates, and
must report its two-generation-arm cost and explicit adapted label.

## Integration evidence

- Focused baseline tests: 24 passed.
- Alignment dry-runs: SynCode, Repilot, and iterative refinement each matched
  67/67 MBJP, 16/16 HumanEval-v15, and 103/103 GFG-v13 rows to the frozen
  scorers.
- Repilot GFG problem 0, greedy, 1024-token cap: produced a complete compiling
  source file, issued real JDT completion queries, and failed the selected
  hidden functional test (0/1). This verifies the execution path without
  treating a smoke result as benchmark accuracy.
- The first full-source SynCode probe ended after four imports because an
  imports-only Java compilation unit is CFG-valid. This probe motivated the
  predeclared production adaptation above: fix the benchmark prompt as the
  decoder prefix and constrain only the unknown continuation, matching
  SynCode's original completion setting.
- A subsequent sampled run exposed upstream SynCode's automatic parser-failure
  fallback on T5Gemma `<unused...>` token paths. The production trajectory now
  records `parser_fallback_to_unconstrained`; results must report this count
  and cannot be described as an unconditional syntax guarantee.
- Iterative GFG problem 47, greedy, two repairs: `3` model calls, `2` repair
  calls, `2,518` input tokens, `3,075` output tokens, `80.13` seconds, and no
  hidden-test exposure. The compile sequence was `false -> false -> false`;
  each round retained an unclosed-comment error. This is direct evidence of
  the frozen model's repair-prompt distribution mismatch.

## Execution and current results

The reproducible launcher is:

```bash
PROOFT5_BASELINE_GPU=0 \
  baselines/java_baselines/run_frozen_t5gemma_baseline.sh \
  <ordinary|syncode|repilot|iterative> <mbjp|humaneval|gfg> <new_output_tag>
```

SynCode may be operationally sharded by task (`--indices`) and global rank
(`--candidate_ranks`) under `--resume`; the seed formula continues to use the
full candidate count, so sharding does not change declared candidate identity.

The paper-facing RQ3 comparison uses MBJP only. All rows below use the archived
paper-recovery checkpoint and the same ten ordered candidate identities. A
cell reports `pass@1 / pass@10 [compile-error candidates]`.

| benchmark | SynCode + compile-safe gate | Repilot/JDT | controlled iterative refinement | Qwen2.5-Coder-3B ordinary | ProofT5 (ours) |
|---|---:|---:|---:|---:|---:|
| MBJP (67) | **10 / 24 [73]** | **10 / 23 [112]** | **8 / 17 [83]** | **26 / 39 [57]** | **17 / 29 [3]** |

The matched ordinary T5Gemma2 control is 10/23 with 122 compilation errors;
it is retained as the attribution control for SynCode and Repilot rather than
as a requested strong-baseline column. Qwen uses a different 3.09B
decoder-only architecture and therefore is an absolute-performance baseline,
not a matched-weight decoding ablation.

The submitted ordinary row is approximately 12/67 and 24/67 (17.91% and
35.82%). Thus the archived checkpoint and matched sampling control reproduce
the paper scale, especially pass@10, without a new checkpoint sweep. The
historical recovery selection did use MBJP test metrics and remains labelled
paper-checkpoint recovery rather than unbiased model selection.

The former negative SynCode result was an invalid adapter result. The
precomputed mask omitted T5Gemma pure-newline tokens even when the Java parser
explicitly allowed ignored whitespace. After repairing that transition, the
full Java grammar accepts 608/608 known-correct MBJP training programs, and the
actual mask retains all 1,909 replayed tokens in a fixed 16-program training
sample. It also retains every token in the ordinary model's 23 first-success
test trajectories. The proposal-preserving grammar-only run therefore exactly
preserves the ordinary solved sets, 10/67 and 23/67.

Upstream-style pre-mask sampling is retained only as a diagnostic. Masking
before multinomial sampling renormalizes the entire distribution, so a fixed
seed can lose a finite-budget successful sample even when no successful token
is rejected. The proposal-preserving adaptation instead samples from the
matched ordinary distribution first and resamples only after an actual grammar
rejection, matching the Repilot control semantics.

The main-table SynCode row adds a transparent compile-safe gate. For each rank,
it retains the ordinary candidate unless standalone `javac` rejects it and
accepts the corresponding SynCode candidate. No benchmark test is executed
during selection. This replaces 68/670 candidates, preserves all ordinary
successes by construction, adds one solved task at pass@10, and reduces scorer
compile errors from 122 to 73. It must be labelled **SynCode + standalone-
`javac` compile-safe portfolio**, not unmodified upstream SynCode, and it costs
two generation arms.

Repilot's corrected search restores untried top-k support when JDT rejects the
entire top-p support. It exactly preserves the ordinary solved sets while
reducing compile errors from 122 to 112. It makes 18,653 real JDT queries,
rejects 1,127 proposed tokens in 56 candidates, and spends 150.44 seconds in
JDT, or 2.66 ms per output token. Its summed candidate time is 1,687.63 seconds
versus 1,509.77 seconds for ordinary generation, an 11.8% increase.

The stricter requested policy that calls `newCompletion` on every token was
rejected by a training-only soundness gate: it falsely prunes 56/608
known-correct Java programs, frequently at a legal `else`. The upstream
keyword/punctuation bypass is therefore required because `newCompletion` is
an IDE autocomplete-feasibility endpoint rather than a Java parser. Every
accepted output token still updates the JDT document; the formal run makes a
completion query only on the 18,653 nontrivial tokens. An equal two-arm
standalone-`javac` portfolio replaces 12 ordinary candidates but remains
10/67 and 23/67, with 110/670 scorer compile errors. Thus it does not reproduce
SynCode portfolio's one-task pass@10 gain.

The artifact's optional `ACTIVE=1` path was subsequently restored in the
adapter and audited before any paper-facing rerun. It propagates the longest
common prefix of JDT autocomplete suggestions, but this is not a sound syntax
constraint: a complete token replay over all 608 known-correct clean MBJP
training programs falsely prunes 293 programs. The formal runner therefore
keeps active completion disabled. The aggregate and six source-shard hashes
are frozen in
`artifacts/major_revision_mbjp_baselines_20260825/repilot_active_completion_training_replay_audit.json`.
This also invalidates the assumption that `newCompletion` subsumes `javac`;
Repilot is an IDE completion-feasibility heuristic and can still emit
syntactically invalid complete files.

Proposal-preserving SynCode takes 5,054.24 summed candidate seconds, including
2,742.65 seconds in 63,821 grammar-mask calls. The compile-safe portfolio costs
6,954.33 seconds when both generation arms and 329.67 seconds of standalone
compilation are counted. These costs are reported explicitly; the accuracy
gain is not compute-matched. ProofT5 remains highest among these matched
T5Gemma2 decoding controls at 17/67 pass@1 and 29/67 pass@10, with only 3/670
compile-error candidates; the separate Qwen decoder-only extension is reported
below.

The controlled iterative run is complete on all 67 MBJP problems with ten
ordered candidates per problem. Its exact exported round-0 control and final
outputs both solve 8/67 at pass@1 and 17/67 at pass@10. Compiler feedback does
repair 68 initially non-compiling candidates and lowers scorer compile errors
from 133/670 to 83/670, but none of those repairs adds a functionally solved
problem. The run makes 945 model calls, of which 275 are repair calls, and
spends 8,461.70 summed candidate seconds. Because its chat-style repair prompt
has a separately exported initial-generation control, functional attribution
must compare final iterative output to that exact 8/17 round-0 row, not to the
10/23 matched-sampling row generated by the direct decoder loop.

## Decoder-only extension protocol (started 2026-08-25)

The modern decoder-only extension uses Qwen2.5-Coder-3B Base (3.09B
parameters). Both arms retain the same 673-row clean Java boundary, frozen
ProofT5 DSL vocabulary and targets, and causal Qwen backbone. Natural-language
inputs use the Qwen tokenizer; DSL embeddings are initialized as the mean Qwen
embedding of each frozen DSL token string. The ordinary arm conditions on the
natural-language input and fixed DSL prefix. The CoqView arm adds a learned
projection of the currently available Coq type-context embedding only to the
causal input position used to predict the next DSL token; it has no encoder and
sees no future CoqView state. The formal adapter uses a zero-initialized
projection and unit scalar gate, so it exactly matches ordinary logits
initially while giving the projection a nonzero first-step gradient. The
formal representation-only continuation freezes the selected ordinary Qwen
backbone and DSL embedding/output table and trains only the projection/gate at
learning rate 1e-5. Earlier gate-initialization, full-model-drift, and
feature-only-1e-4 diagnostics are preserved but excluded by training-side
soundness/loss checks before MBJP test generation.
Full-sample forward/backward, AdamW update, cached generation, and beam-cache
reorder smoke tests passed before training.

Checkpoint candidates are fixed to epoch 5, 10, 15, 20, and final. Selection
uses global training-token loss only; MBJP test generation is prohibited until
both checkpoint selections have been frozen. The implementation and launch
paths are `ModelQwenCausalDsl.py`, `prepare_qwen_causal_dsl_java.py`, and
`baselines/java_baselines/run_qwen_causal_dsl_experiment.sh`.

Both selections are now frozen at the final epoch: ordinary global
training-token loss 0.0179775 and CoqView feature-only loss 0.0206996. The
complete ordinary MBJP evaluation obtains 26/67 pass@1 and 39/67 pass@10,
with 57/670 compilation errors and no missing candidates. This is stronger in
absolute accuracy than the T5Gemma2 ProofT5 row (17/29), so the manuscript
must present Qwen as a stronger architecture/training baseline rather than
claiming universal state of the art. The matched CoqView arm obtains 25/67
pass@1 and 41/67 pass@10. It has 4 compilation errors among 643 materialized
candidates, one Java test timeout, and 27 empty beam-budget positions across
seven tasks; all 67 tasks have a top-1 output. The empty positions exactly
match the per-task beam metadata and are constrained-search exhaustion, not
missing shards.

Against ordinary Qwen, CoqView loses one top-1 task and gains two net top-10
tasks. At pass@10 it adds five tasks and loses three (two-sided exact McNemar
p=0.7266); at pass@1 it adds none and loses one (p=1.0). The controlled result
therefore shows substantially fewer compilability failures and a small but
statistically non-significant pass@10 increase, not stable functional evidence
on the stronger decoder-only checkpoint.

Observed time to the last output was 509.12 seconds for ordinary Qwen and
8,249.50 seconds for CoqView under dynamically expanded fixed-index sharding.
The CoqView figure exposes the cost of real token-level `coqc` checks, but is
not compute-matched because aggregate GPU-worker/CPU/checker process-seconds
were not instrumented.

Controlled iterative refinement and its exact exported round-0 control are now
complete on all three Java evaluation sets:

| benchmark | round-0 pass@1 / pass@10 [compile errors] | final pass@1 / pass@10 [compile errors] | repair calls |
|---|---:|---:|---:|
| HumanEval-v15 (16) | 2 / 2 [46/160] | 2 / 2 [27/160] | 81 |
| MBJP (67) | 8 / 17 [133/670] | 8 / 17 [83/670] | 275 |
| GFG-v13 (103) | 12 / 23 [190/1030] | 12 / 24 [118/1030] | 357 |

Across the three settings, compiler diagnostics consistently improve
compilability, but functional gains are not stable: no new solved problem on
HumanEval or MBJP and one additional pass@10 problem on GFG. The final GFG run
has no missing candidates, makes 1,387 model calls, repairs 83 initially
non-compiling candidates, and spends 14,946.69 summed candidate seconds. The
failed first GFG merge is retained separately: its source shard had all 210
candidates but no terminal manifest, so the fail-closed merger refused it and
the accidental follow-on score recorded 1,030 missing candidates. The
`merged_complete` artifact is the only valid GFG iterative result.

## Manuscript changes after complete scores

No manuscript file is changed by this work. Once complete scores exist, add a
single strong-baseline table with pass@1, pass@10, compilation-error rate, and
cost. Within the matched T5Gemma2 decoding controls ProofT5 is highest at
17/67 pass@1 and 29/67 pass@10; the separate Qwen2.5-Coder-3B ordinary arm is
higher at 26/67 and 39/67 and must remain clearly distinguished. Describe
SynCode as context-free grammar masking and Repilot as a
benchmark/model adapter around its modified-JDT pruning mechanism, not as an
unchanged Defects4J run. Remove the submitted claim that rejection sampling is
functionally equivalent to SynCode. State explicitly that logical/type
constraints, CFG masking, IDE completion pruning, and compiler-feedback repair
use different information and are not equivalent mechanisms.
